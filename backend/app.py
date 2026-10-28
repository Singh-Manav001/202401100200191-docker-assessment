import os
import socket
import time
from contextlib import closing

import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)

REGNO = os.getenv("REGNO", "NOT-SET")
APP_VERSION = os.getenv("APP_VERSION", "dev")

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS registrations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    event TEXT NOT NULL,
    created TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

def connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("POSTGRES_DB", "festpass"),
        user=os.getenv("POSTGRES_USER", "festpass"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=3,
    )

def init_db():
    for attempt in range(10):
        try:
            with closing(connect()) as conn:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(TABLE_SQL)
            return True
        except psycopg2.Error:
            if attempt == 9:
                return False
            time.sleep(2)
    return False

@app.get("/api/health")
def health():
    try:
        with closing(connect()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        database = True
    except psycopg2.Error:
        database = False

    return jsonify(
        service="festpass-backend",
        regno=REGNO,
        version=APP_VERSION,
        container=socket.gethostname(),
        database=database,
    )

@app.get("/api/registrations")
def list_registrations():
    try:
        with closing(connect()) as conn:
            with conn.cursor() as cur:
                cur.execute(TABLE_SQL)
                cur.execute(
                    "SELECT id, name, event, created FROM registrations ORDER BY id"
                )
                rows = cur.fetchall()
        return jsonify([
            {
                "id": row[0],
                "name": row[1],
                "event": row[2],
                "created": row[3].isoformat(timespec="seconds"),
            }
            for row in rows
        ])
    except psycopg2.Error:
        return jsonify(error="database unavailable"), 503

@app.post("/api/registrations")
def add_registration():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    event = str(data.get("event", "")).strip()

    if not name or not event:
        return jsonify(error="name and event are required"), 400

    try:
        with closing(connect()) as conn:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(TABLE_SQL)
                    cur.execute(
                        "INSERT INTO registrations (name, event) VALUES (%s, %s) RETURNING id",
                        (name, event),
                    )
                    new_id = cur.fetchone()[0]
        return jsonify(id=new_id, name=name, event=event), 201
    except psycopg2.Error:
        return jsonify(error="database unavailable"), 503

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
