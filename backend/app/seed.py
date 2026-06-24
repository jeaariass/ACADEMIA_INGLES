import os
from . import db
from .models import User, Level, Topic, Question


def ensure_user(username, full_name, role, password):
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, full_name=full_name, role=role)
        user.set_password(password)
        db.session.add(user)
    return user


def seed_initial_data():
    ensure_user(os.getenv("ADMIN_USERNAME", "admin"), "Administrador", "admin", os.getenv("ADMIN_PASSWORD", "Admin123*"))
    ensure_user(os.getenv("STUDENT1_USERNAME", "estudiante1"), "Estudiante 1", "student", os.getenv("STUDENT1_PASSWORD", "Estudiante123*"))
    ensure_user(os.getenv("STUDENT2_USERNAME", "estudiante2"), "Estudiante 2", "student", os.getenv("STUDENT2_PASSWORD", "Estudiante123*"))

    if not Level.query.filter_by(code="A1").first():
        a1 = Level(code="A1", name="Beginner", description="Nivel inicial: saludos, presente simple, vocabulario cotidiano.")
        db.session.add(a1)
        db.session.flush()
        t1 = Topic(level_id=a1.id, title="Greetings and verb to be", theory="En este tema se estudian saludos básicos y el verbo to be. Ejemplos: I am Ana, You are a student, She is happy.")
        db.session.add(t1)
        db.session.flush()
        questions = [
            ("Choose the correct sentence:", "She are happy", "She is happy", "She am happy", "She be happy", "B", "Con she/he/it se usa is."),
            ("How do you say 'Buenos días' in English?", "Good night", "Good morning", "Good afternoon", "Good bye", "B", "Good morning significa buenos días."),
            ("Complete: I ___ a student.", "is", "are", "am", "be", "C", "Con I se usa am."),
        ]
        for q in questions:
            db.session.add(Question(topic_id=t1.id, prompt=q[0], option_a=q[1], option_b=q[2], option_c=q[3], option_d=q[4], correct_option=q[5], explanation=q[6]))

    if not Level.query.filter_by(code="A2").first():
        a2 = Level(code="A2", name="Elementary", description="Nivel elemental: pasado simple, rutinas, conversaciones breves.")
        db.session.add(a2)
        db.session.flush()
        t2 = Topic(level_id=a2.id, title="Simple Past", theory="El pasado simple se usa para acciones finalizadas. Ejemplo: I visited Bogotá yesterday. En verbos regulares se agrega -ed; en irregulares cambia la forma.")
        db.session.add(t2)
        db.session.flush()
        db.session.add(Question(topic_id=t2.id, prompt="Complete: Yesterday, I ___ English.", option_a="study", option_b="studied", option_c="studies", option_d="studying", correct_option="B", explanation="Yesterday indica pasado; study cambia a studied."))

    db.session.commit()
