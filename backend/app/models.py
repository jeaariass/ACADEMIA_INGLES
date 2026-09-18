from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    learning_mode = db.Column(db.String(20), nullable=False, default="standard")
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_kids_mode(self):
        return self.role != "admin" and self.learning_mode == "kids"


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
    # Legacy/global difficulty used by the original content bank.
    difficulty = db.Column(db.Integer, nullable=False, default=1)
    # Difficulty relative to the question's own CEFR level. This is the field
    # used by the adaptive assessment engine (1=easier within level, 5=harder).
    level_difficulty = db.Column(db.Integer, nullable=False, default=3)
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


class UserTopicPlan(db.Model):
    __table_args__ = (
        db.UniqueConstraint("user_id", "topic_id", name="uq_user_topic_plan_user_topic"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    diagnostic_attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("assessment_attempt.id"),
        nullable=True,
    )
    status = db.Column(db.String(20), nullable=False, default="optional")
    evidence_correct = db.Column(db.Integer, nullable=False, default=0)
    evidence_total = db.Column(db.Integer, nullable=False, default=0)
    evidence_percentage = db.Column(db.Float, nullable=True)
    rationale = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User")
    topic = db.relationship("Topic")
    diagnostic_attempt = db.relationship("AssessmentAttempt", foreign_keys=[diagnostic_attempt_id])


class LibraryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    level_code = db.Column(db.String(10), nullable=False, default="A1")
    category = db.Column(db.String(40), nullable=False, default="story")
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=False, default="")
    content_text = db.Column(db.Text, nullable=False)
    source_label = db.Column(db.String(160), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedVocabulary(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "normalized_text",
            name="uq_saved_vocabulary_user_text",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    library_item_id = db.Column(
        db.Integer,
        db.ForeignKey("library_item.id"),
        nullable=True,
    )
    text = db.Column(db.String(220), nullable=False)
    normalized_text = db.Column(db.String(220), nullable=False)
    translation = db.Column(db.String(500), nullable=False, default="")
    context_text = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    review_stage = db.Column(db.Integer, nullable=False, default=0)
    mastery_level = db.Column(db.Integer, nullable=False, default=0)
    correct_reviews = db.Column(db.Integer, nullable=False, default=0)
    incorrect_reviews = db.Column(db.Integer, nullable=False, default=0)
    next_review_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_reviewed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship("User")
    library_item = db.relationship("LibraryItem")


class GameRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    difficulty_tier = db.Column(db.Integer, nullable=False, default=1)
    completion_number = db.Column(db.Integer, nullable=False, default=1)
    target_distance = db.Column(db.Integer, nullable=False, default=1700)
    target_difficulty = db.Column(db.Integer, nullable=False, default=2)
    level_code = db.Column(db.String(10), nullable=False, default="A1")
    score = db.Column(db.Integer, nullable=False, default=0)
    distance = db.Column(db.Float, nullable=False, default=0.0)
    energy_end = db.Column(db.Float, nullable=False, default=100.0)
    questions_answered = db.Column(db.Integer, nullable=False, default=0)
    correct_answers = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="in_progress")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")
    challenges = db.relationship(
        "GameChallenge",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="GameChallenge.id",
    )


class GameChallenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_run_id = db.Column(db.Integer, db.ForeignKey("game_run.id"), nullable=False)
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("question.id", ondelete="SET NULL"),
        nullable=True,
    )
    saved_vocabulary_id = db.Column(
        db.Integer,
        db.ForeignKey("saved_vocabulary.id", ondelete="SET NULL"),
        nullable=True,
    )
    game_vocabulary_id = db.Column(
        db.Integer,
        db.ForeignKey("game_vocabulary.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type = db.Column(db.String(20), nullable=False, default="curriculum")
    source_label = db.Column(db.String(220), nullable=False, default="Curriculum")
    skill = db.Column(db.String(30), nullable=False, default="grammar")
    prompt = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    explanation = db.Column(db.Text, nullable=False, default="")
    difficulty = db.Column(db.Integer, nullable=False, default=3)
    selected_option = db.Column(db.String(1), nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime, nullable=True)

    run = db.relationship("GameRun", back_populates="challenges")
    question = db.relationship("Question")
    saved_vocabulary = db.relationship("SavedVocabulary")
    game_vocabulary = db.relationship("GameVocabulary")


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


class SpeakingExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    level_code = db.Column(db.String(10), nullable=False, default="A1")
    activity_type = db.Column(db.String(30), nullable=False, default="repeat")
    title = db.Column(db.String(180), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False, default="")
    expected_text = db.Column(db.Text, nullable=True)
    target_vocabulary = db.Column(db.JSON, nullable=False, default=list)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SpeakingAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("speaking_exercise.id"), nullable=False)
    transcript = db.Column(db.Text, nullable=False, default="")
    recognition_confidence = db.Column(db.Float, nullable=True)
    duration_seconds = db.Column(db.Float, nullable=True)
    similarity_score = db.Column(db.Float, nullable=True)
    token_coverage = db.Column(db.Float, nullable=True)
    words_per_minute = db.Column(db.Float, nullable=True)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    target_hits = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
    exercise = db.relationship("SpeakingExercise")


class WritingPrompt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    level_code = db.Column(db.String(10), nullable=False, default="A1")
    title = db.Column(db.String(180), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False, default="")
    min_words = db.Column(db.Integer, nullable=False, default=30)
    max_words = db.Column(db.Integer, nullable=False, default=80)
    target_vocabulary = db.Column(db.JSON, nullable=False, default=list)
    target_connectors = db.Column(db.JSON, nullable=False, default=list)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WritingSubmission(db.Model):
    __table_args__ = (
        db.UniqueConstraint("user_id", "prompt_id", "revision_number", name="uq_writing_revision"),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    prompt_id = db.Column(db.Integer, db.ForeignKey("writing_prompt.id"), nullable=False)
    revision_number = db.Column(db.Integer, nullable=False, default=1)
    content_text = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    sentence_count = db.Column(db.Integer, nullable=False, default=0)
    unique_word_ratio = db.Column(db.Float, nullable=True)
    target_hits = db.Column(db.Integer, nullable=False, default=0)
    connector_hits = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
    prompt = db.relationship("WritingPrompt")


class ArcadeRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    game_type = db.Column(db.String(40), nullable=False)
    level_code = db.Column(db.String(10), nullable=False, default="A1")
    score = db.Column(db.Integer, nullable=False, default=0)
    rounds_total = db.Column(db.Integer, nullable=False, default=0)
    rounds_correct = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="in_progress")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")
    challenges = db.relationship(
        "ArcadeChallenge",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ArcadeChallenge.id",
    )


class ArcadeChallenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    arcade_run_id = db.Column(db.Integer, db.ForeignKey("arcade_run.id"), nullable=False)
    source_type = db.Column(db.String(30), nullable=False, default="question")
    source_id = db.Column(db.Integer, nullable=True)
    prompt = db.Column(db.Text, nullable=False)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    correct_answer = db.Column(db.Text, nullable=False)
    selected_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime, nullable=True)

    run = db.relationship("ArcadeRun", back_populates="challenges")


class GameVocabularyCategory(db.Model):
    __tablename__ = "game_vocabulary_category"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    visual = db.Column(db.String(40), nullable=False, default="🎮")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    kids_enabled = db.Column(db.Boolean, nullable=False, default=True)
    standard_enabled = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    words = db.relationship(
        "GameVocabulary",
        back_populates="category",
        order_by="GameVocabulary.sort_order, GameVocabulary.id",
    )


class GameVocabulary(db.Model):
    __tablename__ = "game_vocabulary"
    __table_args__ = (
        db.CheckConstraint("kids_difficulty BETWEEN 1 AND 3", name="ck_game_vocab_kids_difficulty"),
        db.CheckConstraint("standard_difficulty BETWEEN 1 AND 5", name="ck_game_vocab_standard_difficulty"),
    )

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("game_vocabulary_category.id"), nullable=False)
    english = db.Column(db.String(160), nullable=False)
    spanish = db.Column(db.String(160), nullable=False)
    visual = db.Column(db.String(80), nullable=False, default="✨")
    kids_difficulty = db.Column(db.Integer, nullable=False, default=1)
    cefr_level = db.Column(db.String(10), nullable=False, default="A1")
    standard_difficulty = db.Column(db.Integer, nullable=False, default=1)
    kids_enabled = db.Column(db.Boolean, nullable=False, default=True)
    standard_enabled = db.Column(db.Boolean, nullable=False, default=True)
    kids_games = db.Column(db.JSON, nullable=False, default=list)
    arcade_games = db.Column(db.JSON, nullable=False, default=list)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = db.relationship("GameVocabularyCategory", back_populates="words")



class KidsGameRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    game_type = db.Column(db.String(40), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="first_words")
    theme = db.Column(db.String(30), nullable=False, default="jungle")
    stars = db.Column(db.Integer, nullable=False, default=0)
    rounds_total = db.Column(db.Integer, nullable=False, default=0)
    rounds_success = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")


class KidsWordProgress(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", "word_key", name="uq_kids_word_progress_user_word"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    word_key = db.Column(db.String(80), nullable=False)
    exposures = db.Column(db.Integer, nullable=False, default=0)
    successes = db.Column(db.Integer, nullable=False, default=0)
    last_seen_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")
