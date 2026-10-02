"""智学英语 Android 本地服务入口（p4a service bootstrap 调用）。

路线复用《智学小四门》已验证实现：p4a（python-for-android，service_library bootstrap）
把 CPython + 本载荷打成 AAR；Android 侧 ServiceZhixue.prepare()/start() 解包并启动本文件。

入口 = **正式 Web（web/app.py）**，127.0.0.1:8770。

P6-B-2C：learning DB 的 seed / state 分离
  * 载荷内只有 **clean seed**：`<files>/app/structured/learning/learning.clean-seed.db`（只读，永不写入）
  * 运行时 state DB：`<files>/state/learning.db`
  * 仅当 state DB **不存在** 时，从 seed 复制一次（绝不覆盖已有 state，payload 更新也不覆盖）
  * 复制完成后立即做**只读**校验（user_version / schema_migration / learner / integrity / foreign_key）；
    任一不通过即 **显式失败**，不启动 Web —— 绝不让 sqlite3.connect() 静默创建空库
  * 正式 Web 通过 `--db <state>` 显式使用 state DB（不用默认值）

边界：
  * 监听 127.0.0.1（仅本机，不暴露局域网）；
  * 通过 ZX_ROOT 让 web/learning 代码以本载荷目录为根（Windows 上默认值不变）；
  * 不重写任何业务逻辑、路由与页面；不新增 migration。
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import sqlite3
import sys
import zipfile

APP_ROOT = pathlib.Path(__file__).resolve().parent.parent      # <files>/app（p4a 解包后的载荷根）
FILES_DIR = APP_ROOT.parent                                    # <files>
WEB_DIR = APP_ROOT / "web"
LEARNING_DIR = APP_ROOT / "learning"

#: 载荷内 clean seed（只读；永不当运行时库使用）
SEED_DB = APP_ROOT / "structured" / "learning" / "learning.clean-seed.db"
#: 运行时 state（持久化目录，不在 payload 的清理范围内）
STATE_DIR = FILES_DIR / "state"
STATE_DB = STATE_DIR / "learning.db"
#: 正式教材内容库（只读）
CONTENTPACK_DB = APP_ROOT / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

#: 官方 MP3 以短名 zip 随载荷分发（原始文件名过长，进不了 p4a 的 ustar private.tar）
OFFICIAL_AUDIO_ZIP = APP_ROOT / "official_audio.zip"
OFFICIAL_AUDIO_MARK = APP_ROOT / "official_audio.version"

EXPECTED_USER_VERSION = 2
EXPECTED_MIGRATION_ROWS = 2

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8770


# --------------------------------------------------------------------------- 只读校验 / 首次播种

def verify_learning_db(path, expect_empty_learner: bool = True) -> list:
    """对学习库做**只读**结构校验（`mode=ro` 不会创建文件）；返回问题列表（空 = 通过）。"""
    problems = []
    path = pathlib.Path(path)
    if not path.is_file():
        return ["文件不存在：%s" % path]
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % path.as_posix(), uri=True)
    except Exception as exc:                             # noqa: BLE001
        return ["无法以只读方式打开：%r" % exc]
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != EXPECTED_USER_VERSION:
            problems.append("user_version=%s（应为 %d）" % (version, EXPECTED_USER_VERSION))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "schema_migration" not in tables:
            problems.append("缺少 schema_migration 表")
        else:
            rows = conn.execute("SELECT COUNT(*) FROM schema_migration").fetchone()[0]
            if rows != EXPECTED_MIGRATION_ROWS:
                problems.append("schema_migration=%d 行（应为 %d）" % (rows, EXPECTED_MIGRATION_ROWS))
        if "learner" not in tables:
            problems.append("缺少 learner 表")
        elif expect_empty_learner:
            learners = conn.execute("SELECT COUNT(*) FROM learner").fetchone()[0]
            if learners != 0:
                problems.append("learner=%d 行（seed 应为 0）" % learners)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            problems.append("integrity_check=%s" % integrity)
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            problems.append("foreign_key_check=%d 行" % len(fk))
    except Exception as exc:                             # noqa: BLE001
        problems.append("校验查询失败：%r" % exc)
    finally:
        conn.close()
    return problems


def seed_state_db() -> str:
    """首次运行播种 state DB；成功返回空串，失败返回原因（调用方必须停止启动 Web）。"""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:                             # noqa: BLE001
        return "无法创建 state 目录 %s：%r" % (STATE_DIR, exc)

    if STATE_DB.exists():
        print("[state] 已存在运行时学习库，跳过播种：%s" % STATE_DB)
        return ""

    if not SEED_DB.is_file():
        return "clean seed 缺失：%s（不创建空库）" % SEED_DB

    seed_problems = verify_learning_db(SEED_DB)
    if seed_problems:
        return "clean seed 校验失败：%s" % "；".join(seed_problems)

    tmp = STATE_DB.parent / (STATE_DB.name + ".tmp")
    try:
        shutil.copyfile(SEED_DB, tmp)                    # 纯文件复制，不打开 seed 写库
        os.replace(tmp, STATE_DB)
    except Exception as exc:                             # noqa: BLE001
        try:
            tmp.unlink(missing_ok=True)
        except Exception:                                # noqa: BLE001
            pass
        return "播种失败：%r" % exc

    state_problems = verify_learning_db(STATE_DB)
    if state_problems:
        try:
            STATE_DB.unlink(missing_ok=True)             # 回滚，下次启动重试
        except Exception:                                # noqa: BLE001
            pass
        return "播种后 state 校验失败（已回滚）：%s" % "；".join(state_problems)

    print("[state] 首次播种完成：%s → %s" % (SEED_DB, STATE_DB))
    return ""


# --------------------------------------------------------------------------- 官方音频（沿用既有机制）

def _unpack_official_audio() -> bool:
    """把 official_audio.zip 解包回 `<载荷根>/<官方目录>/`（与 PC 上的目录结构完全一致）。

    幂等：zip 大小/时间未变时跳过；解包失败不阻塞服务（只是听音类没有音频）。
    """
    if not OFFICIAL_AUDIO_ZIP.exists():
        return False
    stamp = "%d-%d" % (OFFICIAL_AUDIO_ZIP.stat().st_size, int(OFFICIAL_AUDIO_ZIP.stat().st_mtime))
    try:
        if OFFICIAL_AUDIO_MARK.exists() and OFFICIAL_AUDIO_MARK.read_text().strip() == stamp:
            return True
        with zipfile.ZipFile(OFFICIAL_AUDIO_ZIP) as zf:
            zf.extractall(APP_ROOT)
        OFFICIAL_AUDIO_MARK.write_text(stamp, encoding="utf-8")
        return True
    except Exception as exc:                             # noqa: BLE001 —— 音频缺失不阻塞学习功能
        print("WARN: 官方音频解包失败：%s" % exc)
        return False


# --------------------------------------------------------------------------- 启动正式 Web

def _load_web_app():
    """按显式路径加载正式 Web 入口（避免与载荷根同名目录冲突）。"""
    path = WEB_DIR / "app.py"
    spec = importlib.util.spec_from_file_location("zhixue_web_app", path)
    if spec is None or spec.loader is None:
        raise ImportError("无法加载正式 Web 入口：%s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["zhixue_web_app"] = module
    spec.loader.exec_module(module)
    return module


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """首次播种 state DB → 启动正式 Web（web/app.py），显式使用 state DB。"""
    reason = seed_state_db()
    if reason:
        print("STOP: %s" % reason)
        return 2

    # 现有 web/learning 代码用 ZX_ROOT 解析项目根（指向只读载荷；学习库由 --db 显式指定）
    os.environ.setdefault("ZX_ROOT", str(APP_ROOT))
    sys.dont_write_bytecode = True
    for _p in (str(WEB_DIR), str(LEARNING_DIR)):
        if _p not in sys.path:
            sys.path.insert(0, _p)

    # 官方音频解包（大文件）放后台线程：等服务先起来再解包，避免拖慢首次探活
    import threading
    import time

    def _later() -> None:
        time.sleep(5.0)
        _unpack_official_audio()

    threading.Thread(target=_later, name="official-audio", daemon=True).start()

    print("[web] learning.db (state) = %s" % STATE_DB)
    print("[web] contentpack        = %s" % CONTENTPACK_DB)
    sys.argv = ["app.py", "--host", host, "--port", str(port),
                "--db", str(STATE_DB), "--contentpack", str(CONTENTPACK_DB)]
    return _load_web_app().main()


if __name__ == "__main__":
    raise SystemExit(run())
