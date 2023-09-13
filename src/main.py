from datetime import datetime
from flask import Flask, g, request, flash
import sqlite3
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
from pydantic import UUID4, BaseModel, FutureDatetime, Field
import uuid

app = Flask(__name__)

key = uuid.uuid4().hex
app.secret_key = key
connection = sqlite3.connect("app.db")
list_length: int = 0


DATABASE_PATH = "app.db"
create = """
    CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    note TEXT NOT NULL,
    creation_date INTEGER NOT NULL,
    deadline INTEGER,
    alert_level INTEGER NOT NULL,
    status INTEGER NOT NULL
    );
"""

insert = "INSERT INTO notes (id, note, creation_date, deadline, alert_level, status) VALUES (?, ?, ?, ?, ?, ?)"

env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape())


class Note(BaseModel):
    id: UUID4 = uuid.uuid4()
    # constr(strip_whitespace=True, max_length=200)
    note: str = Field(max_length=200)
    creation_date: datetime = datetime.now()
    deadline: FutureDatetime | None = None
    alert_level: int = Field(ge=0, le=2, default=2)
    status: int = 0


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.execute(create)
        g.db.commit()
    return g.db


@app.route("/", methods=["GET"])
def index():
    table = env.get_template("list.html")
    items = get_all()
    global list_length
    list_length = len(items)
    headers = {"HX-Redirect": "/"}
    return table.render({"items": items}), 200, headers


@app.route("/new_note", methods=["POST"])
def add_note():
    note = Note(id=uuid.uuid4(), note=request.form.get("note", ""))
    db = get_db()
    try:
        db.execute(
            insert,
            (
                str(note.id),
                note.note,
                note.creation_date,
                note.deadline,
                note.alert_level,
                note.status,
            ),
        )
        db.commit()
    except BaseException:
        print("not a unique id: ", note.id)
    flash("New note created successfully")

    global list_length
    list_length += 1
    return create_li(list_length, note)


@app.route("/note", methods=["POST"])
def done_note():
    id = request.form.get("id")
    if not id:
        return "", 404
    status = get_status(id)
    if status == 1:
        status = 0
    else:
        status = 1
    db = get_db()
    db.execute("UPDATE notes SET status = (?) WHERE id=(?)", (status, id))
    db.commit()
    note = get_note(id)
    return crossover(note, status)


def get_status(id: str) -> int:
    db = get_db()
    cursor = db.execute("SELECT status FROM notes WHERE id=(?)", (str(id),))
    status = cursor.fetchone()[0]
    return status


def get_note(id: str) -> str:
    db = get_db()
    cursor = db.execute("SELECT note FROM notes WHERE id=(?)", (str(id),))
    note = cursor.fetchone()[0]
    return note


def crossover(text: str, status: int) -> str:
    if status == 1:
        templ = Template("<s>{{note}}</s>")
    else:
        templ = Template("{{note}}")
    return templ.render({"note": text})


def create_li(index: int, item: Note) -> str:
    temp = env.get_template("list_item.html")
    return temp.render({"index": index, "item": item})


def get_all() -> list[Note]:
    notes: list[Note] = []
    db = get_db()
    for row in db.execute("SELECT * FROM notes"):
        print(row)
        notes.append(
            Note(
                id=row[0],
                note=row[1],
                creation_date=row[2],
                deadline=row[3],
                alert_level=row[4],
                status=row[5],
            )
        )
    return notes


@app.route("/note", methods=["DELETE"])
def delete_note():
    id = request.form.get("id")
    if not id:
        return "", 404
    db = get_db()
    db.execute("DELETE FROM notes WHERE id=(?)", (id,))
    db.commit()
    return "", 200
