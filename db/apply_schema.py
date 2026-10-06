"""Apply db/aiven_schema.sql to the Aiven MySQL in .env (MYSQL_DATABASE_URL, MYSQL_SSL_CA).

python db/apply_schema.py            # create missing tables
python db/apply_schema.py --reset    # DROP every table in the database first (destructive)
"""
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql

ROOT = Path(__file__).resolve().parents[1]


def env() -> dict[str, str]:
    values = {}
    dotenv = ROOT / ".env"  # optional: a systemd EnvironmentFile (MYSQL_*) works without it
    for line in (dotenv.read_text(encoding="utf-8").splitlines() if dotenv.exists() else []):
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return {**values, **{k: v for k, v in os.environ.items() if k.startswith("MYSQL_")}}


def connect():
    e = env()
    u = urlparse(e["MYSQL_DATABASE_URL"])
    return pymysql.connect(host=u.hostname, port=u.port, user=u.username, password=unquote(u.password),
                           database=u.path.lstrip("/"), ssl={"ca": e["MYSQL_SSL_CA"]}, autocommit=True)


def main() -> None:
    conn = connect()
    with conn.cursor() as cur:
        if "--reset" in sys.argv:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")  # tables may reference each other
            cur.execute("SHOW TABLES")
            for (table,) in cur.fetchall():
                cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                print(f"drop {table} ({cur.fetchone()[0]} rows)")
                cur.execute(f"DROP TABLE `{table}`")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        sql = (ROOT / "db" / "aiven_schema.sql").read_text(encoding="utf-8")
        body = "\n".join(line.split("--")[0] for line in sql.splitlines())
        for stmt in filter(str.strip, body.split(";")):
            cur.execute(stmt)
        cur.execute("SHOW TABLES")
        print("tables:", [t for (t,) in cur.fetchall()])
    conn.close()


if __name__ == "__main__":
    main()
