#!/usr/bin/env python3
"""Back up and validate MediaIndex before recreating its Compose service."""

import argparse
from contextlib import closing, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time


SERVICE = "media-index"
DEFAULT_DB = "/app/data/media_index.db"
REQUIRED_TABLES = {"tracking_tasks", "transfer_jobs", "wishlist"}
TIMEOUT = 300


class UpgradeError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise UpgradeError(message)


def read_database(path):
    require(path.is_file() and path.stat().st_size > 0, "数据库文件缺失或为空")
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)


def verify_database(path):
    with closing(read_database(path)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(REQUIRED_TABLES <= tables, "文件缺少 MediaIndex 数据表")
        require(connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "SQLite 完整性检查未通过")


def backup_database(source, destination, timeout=TIMEOUT):
    deadline = time.monotonic() + timeout

    def check_time(_status, _remaining, _total):
        require(time.monotonic() < deadline, "SQLite 备份超时，请在写入较少时重试")

    # Work in a private directory so failed or interrupted copies have no final filename.
    require(not destination.exists() and not destination.is_symlink(), "备份文件已存在")
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        staged = Path(directory) / "snapshot.db"
        with closing(read_database(source)) as reader, closing(sqlite3.connect(staged)) as writer:
            reader.backup(writer, pages=256, progress=check_time, sleep=0.1)
            require(writer.execute("PRAGMA journal_mode=DELETE").fetchone() == ("delete",), "无法生成独立备份文件")
        verify_database(staged)
        staged.chmod(0o600)
        os.replace(staged, destination)


def run(args, *, stage, stdin=None, stdout=subprocess.PIPE, data=None, timeout=TIMEOUT):
    try:
        result = subprocess.run(args, input=data, stdin=stdin, stdout=stdout, stderr=subprocess.DEVNULL,
                                timeout=timeout, check=True)
    except (OSError, subprocess.SubprocessError):
        raise UpgradeError(f"{stage}失败") from None
    return result.stdout


def inspect(kind, name):
    output = run(["docker", kind, "inspect", name], stage="读取 Docker 状态")
    return json.loads(output)[0]


def running_container(compose):
    ids = run([*compose, "ps", "-q", SERVICE], stage="寻找运行中的 MediaIndex 容器").decode().split()
    require(len(ids) == 1, "需要一个运行中的 MediaIndex 容器，请核对当前 Compose 项目")
    container = inspect("container", ids[0])
    labels = container["Config"]["Labels"] or {}
    state = container["State"]
    require(labels.get("com.docker.compose.service") == SERVICE
            and labels.get("com.docker.compose.oneoff", "false").lower() == "false"
            and state["Running"] and not state["Restarting"] and not state["Paused"],
            "MediaIndex 容器未处于正常运行状态")
    return container


def compose_config(compose):
    output = run([*compose, "config", "--format", "json"], stage="解析 Compose 配置")
    config = json.loads(output)
    require(SERVICE in config["services"], "Compose 配置缺少 media-index 服务")
    return config


def effective_mount(mounts, db_path, target_key):
    path = PurePosixPath(db_path)
    matches = []
    for mount in mounts:
        target = PurePosixPath(mount[target_key])
        if target.is_absolute() and (path == target or target in path.parents):
            matches.append((len(target.parts), mount))
    require(matches, "数据库未挂载到持久卷")
    return max(matches, key=lambda item: item[0])[1]


def upgrade_target(config, current):
    service = config["services"][SERVICE]
    project = current["Config"]["Labels"].get("com.docker.compose.project")
    require(config.get("name") == project, "运行容器与 Compose 项目不一致")
    db_path = (service.get("environment") or {}).get("DB_PATH") or DEFAULT_DB
    require(PurePosixPath(db_path).is_absolute() and ".." not in PurePosixPath(db_path).parts,
            "请将 DB_PATH 设置为容器内的绝对路径")
    old = effective_mount(current["Mounts"], db_path, "Destination")
    new = effective_mount(service.get("volumes") or [], db_path, "target")
    require(db_path not in (old["Destination"], new["target"]), "请挂载数据库目录，确保 WAL 与数据库一起持久化")
    require(not (new.get("volume") or {}).get("subpath"), "数据库卷使用了子路径，请先核对挂载并手动备份")
    volume = (config.get("volumes") or {}).get(new.get("source"), {})
    source_matches = (new["type"] == "bind" and old["Source"] == new.get("source")
                      or new["type"] == "volume" and old.get("Name") == volume.get("name") and bool(old.get("Name")))
    require(old["Type"] == new["type"] and old["Destination"] == new["target"] and source_matches
            and old["RW"] and not new.get("read_only"), "数据库挂载与当前容器不一致或不可写")
    require(service.get("image"), "Compose 服务缺少镜像")
    return service["image"], db_path


def snapshot_from_container(container, expected_path, directory):
    staged = directory / "media_index.db.partial"
    destination = directory / "media_index.db"
    payload = Path(__file__).read_bytes()
    try:
        with staged.open("xb") as output:
            os.fchmod(output.fileno(), 0o600)
            run(["docker", "exec", "-i", container, "python", "-", "--snapshot", expected_path],
                stage="备份或检查当前数据库", data=payload, stdout=output, timeout=TIMEOUT + 30)
            output.flush()
            os.fsync(output.fileno())
        verify_database(staged)
        os.replace(staged, destination)
    finally:
        if staged.exists():
            staged.unlink()
    return destination


def snapshot_to_stdout(expected_path):
    with redirect_stdout(sys.stderr):
        # docker exec defaults to the image's configured user. Use the service's
        # runtime IDs so SQLite never creates root-owned WAL sidecars.
        if os.geteuid() == 0:
            status = dict(line.split(":", 1) for line in Path("/proc/1/status").read_text().splitlines() if ":" in line)
            uid, gid = int(status["Uid"].split()[1]), int(status["Gid"].split()[1])
            if uid == 0 and status["Name"].strip() == "docker-init":
                uid, gid = int(os.getenv("PUID", "10001")), int(os.getenv("PGID", "10001"))
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
        from app.core.config import Settings

        settings = Settings(_env_file=os.getenv("MEDIA_CONFIG_PATH", ".env"))
        source = Path(settings.db_path)
        require(source == Path(expected_path) and source.resolve() == source, "运行容器的数据库路径与 Compose 不一致")
        with tempfile.TemporaryDirectory(prefix="mediaindex-upgrade-") as directory:
            destination = Path(directory) / "snapshot.db"
            backup_database(source, destination)
            with destination.open("rb") as backup:
                shutil.copyfileobj(backup, sys.__stdout__.buffer)


MIGRATION_CHECK = """
from contextlib import closing
import os, shutil, sqlite3, sys, tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'media_index.db'
    with path.open('wb') as copy:
        shutil.copyfileobj(sys.stdin.buffer, copy)
    os.environ.update(DB_PATH=str(path), MEDIA_CONFIG_PATH=str(path.with_suffix('.env')),
                      CACHE_DIR=str(path.parent / 'cache'))
    from app.db.database import init_db
    init_db()
    with closing(sqlite3.connect(path)) as connection:
        if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('SQLite migration integrity check failed')
"""


def validate_migration(image, snapshot):
    with snapshot.open("rb") as source:
        run(["docker", "run", "--rm", "-i", "--network", "none", "--entrypoint", "python", image,
             "-c", MIGRATION_CHECK], stage="新镜像的离线数据库升级预演", stdin=source, stdout=subprocess.DEVNULL)


STARTUP_CHECK = """
import json, os, urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('http://127.0.0.1:8000/', timeout=2) as response:
    if response.status != 200:
        raise RuntimeError('Management endpoint is not ready')
port = os.environ.get('MEDIA_PLAYBACK_INTERNAL_PORT', '8097')
with opener.open('http://127.0.0.1:' + port + '/health', timeout=2) as response:
    if json.load(response).get('ok') is not True:
        raise RuntimeError('Playback endpoint is not ready')
"""


def wait_for_start(compose, target):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            container = running_container(compose)
            if container["Image"] == target:
                run(["docker", "exec", container["Id"], "python", "-c", STARTUP_CHECK],
                    stage="检查启动状态", timeout=6)
                return
        except UpgradeError:
            pass
        time.sleep(1)
    raise UpgradeError("升级后的容器未通过管理页和播放接口检查")


def upgrade(compose, backup_root):
    current_config = compose_config(compose)
    current = running_container(compose)
    image_ref, db_path = upgrade_target(current_config, current)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=backup_root))
    print("正在备份并检查现有数据库，原容器继续运行。", flush=True)
    snapshot = snapshot_from_container(current["Id"], db_path, folder)
    print(f"已验证数据库备份：{snapshot}", flush=True)

    rollback = f"mediaindex-upgrade-rollback:{folder.name.lower()}"
    run(["docker", "image", "tag", current["Image"], rollback], stage="保留升级前镜像")
    print(f"已保留升级前镜像：{rollback}", flush=True)
    run([*compose, "pull", SERVICE], stage="拉取 MediaIndex 镜像", timeout=1800)
    target = inspect("image", image_ref)["Id"]
    if target == current["Image"]:
        print("运行中的镜像已经是目标版本，数据库备份已保留。")
        return

    print("正在用新镜像验证数据库副本。", flush=True)
    validate_migration(target, snapshot)
    require(compose_config(compose) == current_config and running_container(compose)["Id"] == current["Id"]
            and inspect("image", image_ref)["Id"] == target, "检查期间 Compose、容器或目标镜像发生变化")
    print("检查通过，正在重建 MediaIndex 服务。", flush=True)
    try:
        run([*compose, "up", "-d", "--no-deps", "--no-build", "--pull", "never", SERVICE], stage="重建 MediaIndex")
        wait_for_start(compose, target)
    except UpgradeError:
        print(f"请查看服务日志：{shlex.join([*compose, 'logs', '--tail=100', SERVICE])}", file=sys.stderr)
        print(f"回滚资料：{rollback}、{snapshot}", file=sys.stderr)
        raise
    print("MediaIndex 已通过管理页和播放接口检查。请检查历史任务，并实际播放一个既有 STRM。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-f", "--file", action="append", default=[], help="Compose 文件，可重复指定")
    parser.add_argument("-p", "--project-name", help="现有 Compose 项目名称")
    parser.add_argument("--env-file", action="append", default=[], help="Compose 环境文件，可重复指定")
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("请在 NAS、Linux 或 macOS 的 Docker 宿主机上运行")
    import fcntl

    compose = ["docker", "compose"]
    for flag, values in (("-f", args.file), ("--env-file", args.env_file)):
        for value in values:
            compose.extend((flag, value))
    if args.project_name:
        compose.extend(("-p", args.project_name))
    try:
        backup_root = Path.cwd() / "backups" / "mediaindex-upgrade"
        backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = backup_root / ".upgrade.lock"
        with os.fdopen(os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "wb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            upgrade(compose, backup_root)
    except (UpgradeError, OSError, sqlite3.DatabaseError, ValueError) as error:
        reason = str(error) if isinstance(error, UpgradeError) else type(error).__name__
        print(f"升级中止：{reason}。", file=sys.stderr)
        print("若数据库异常，请保留原 data 目录和同批次 db、-wal、-shm 文件。"
              "优先检查并恢复最近一份健康备份；没有备份时，只在数据库副本上用 SQLite .recover 抢救。"
              "恢复步骤：https://www.sqlite.org/recovery.html", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--snapshot":
        snapshot_to_stdout(sys.argv[2])
    else:
        raise SystemExit(main())
