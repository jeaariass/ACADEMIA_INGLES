from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


class Level(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    topics = db.relationship(
        "Topic",
        backref="level",
        cascade="all, delete-orphan",
        order_by="Topic.sort_order",
    )
    assessments = db.relationship("Assessment", back_populates="level")


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level_id = db.Column(db.Integer, db.ForeignKey("level.id"), nullable=False)
    code = db.Column(db.String(40), unique=True, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    title = db.Column(db.String(160), nullable=False)
    objective = db.Column(db.Text, default="")
    theory = db.Column(db.Text, nullable=False)
    examples = db.Column(db.JSON, nullable=False, default=list)
    common_mistakes = db.Column(db.JSON, nullable=False, default=list)
    key_vocabulary = db.Column(db.JSON, nullable=False, default=list)
    youtube_video_id = db.Column(db.String(80), nullable=True)
    is_published = db.Column(db.Boolean, nullable=False, default=True)

    questions = db.relationship(
        "Question",
        backref="topic",
        cascade="all, delete-orphan",
        order_by="Question.sort_order",
    )
    passages = db.relationship(
        "Passage",
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="Passage.sort_order",
    )


class Passage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    code = db.Column(db.String(60), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    passage_type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    instructions = db.Column(db.Text, default="")
    content_text = db.Column(db.Text, nullable=True)
    audio_text = db.Column(db.Text, nullable=True)
    audio_accent = db.Column(db.String(20), nullable=False, default="en-US")
    audio_rate = db.Column(db.Float, nullable=False, default=1.0)
    max_audio_plays = db.Column(db.Integer, nullable=False, default=2)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    topic = db.relationship("Topic", back_populates="passages")
    questions = db.relationship(
        "Question",
        back_populates="passage",
        order_by="Question.sort_order",
    )


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    passage_id = db.Column(db.Integer, db.ForeignKey("passage.id"), nullable=True)
    code = db.Column(db.String(60), unique=True, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    skill = db.Column(db.String(30), nullable=False, default="grammar")
    question_type = db.Column(db.String(40), nullable=False, default="multiple_choice")
    difficulty = db.Column(db.Integer, nullable=False, default=1)
    prompt = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    explanation = db.Column(db.Text, default="")
    audio_text = db.Column(db.Text, nullable=True)
    audio_accent = db.Column(db.String(20), nullable=False, default="en-US")
    audio_rate = db.Column(db.Float, nullable=False, default=1.0)
    max_audio_plays = db.Column(db.Integer, nullable=False, default=2)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    passage = db.relationship("Passage", back_populates="questions")
    assessment_links = db.relationship(
        "AssessmentQuestion",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
    topic = db.relationship("Topic")
    answers = db.relationship("Answer", backref="attempt", cascade="all, delete-orphan")


class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempt.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)

    question = db.relationship("Question")


class TopicProgress(db.Model):
    __table_args__ = (
        db.UniqueConstraint("user_id", "topic_id", name="uq_topic_progress_user_topic"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)

    completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_practiced_at = db.Column(db.DateTime, nullable=True)

    best_score = db.Column(db.Integer, nullable=False, default=0)
    best_total = db.Column(db.Integer, nullable=False, default=0)
    best_percentage = db.Column(db.Float, nullable=False, default=0.0)

    last_attempt_id = db.Column(db.Integer, db.ForeignKey("attempt.id"), nullable=True)

    user = db.relationship("User")
    topic = db.relationship("Topic")
    last_attempt = db.relationship("Attempt", foreign_keys=[last_attempt_id])


class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    assessment_type = db.Column(db.String(30), nullable=False)
    level_id = db.Column(db.Integer, db.ForeignKey("level.id"), nullable=True)
    description = db.Column(db.Text, default="")
    instructions = db.Column(db.Text, default="")
    duration_minutes = db.Column(db.Integer, nullable=True)
    passing_score = db.Column(db.Float, nullable=True)
    is_adaptive = db.Column(db.Boolean, nullable=False, default=False)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    level = db.relationship("Level", back_populates="assessments")
    question_links = db.relationship(
        "AssessmentQuestion",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentQuestion.sort_order",
    )
    attempts = db.relationship(
        "AssessmentAttempt",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )


class AssessmentQuestion(db.Model):
    __table_args__ = (
        db.UniqueConstraint("assessment_id", "question_id", name="uq_assessment_question"),
    )

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessment.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    section = db.Column(db.String(40), nullable=False, default="general")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    weight = db.Column(db.Float, nullable=False, default=1.0)

    assessment = db.relationship("Assessment", back_populates="question_links")
    question = db.relationship("Question", back_populates="assessment_links")


class AssessmentAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessment.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False, default=0)
    percentage = db.Column(db.Float, nullable=False, default=0.0)
    estimated_level = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="in_progress")

    # Adaptive diagnostic state. Nullable so existing assessment attempts migrate safely.
    current_stage = db.Column(db.String(10), nullable=True)
    diagnostic_direction = db.Column(db.String(20), nullable=True)
    diagnostic_path = db.Column(db.JSON, nullable=True)
    result_profile = db.Column(db.JSON, nullable=True)

    user = db.relationship("User")
    assessment = db.relationship("Assessment", back_populates="attempts")
    answers = db.relationship(
        "AssessmentAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class AssessmentAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assessment_attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("assessment_attempt.id"),
        nullable=False,
    )
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    selected_option = db.Column(db.String(1), nullable=True)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    response_time_seconds = db.Column(db.Integer, nullable=True)
    audio_plays = db.Column(db.Integer, nullable=False, default=0)

    attempt = db.relationship("AssessmentAttempt", back_populates="answers")
    question = db.relationship("Question")
