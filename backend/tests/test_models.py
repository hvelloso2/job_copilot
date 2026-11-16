from app.models import (
    Analysis,
    Application,
    ApplicationStatus,
    GeneratedText,
    Job,
    Profile,
    TextType,
)


def test_profile_persists_json(db) -> None:
    profile = Profile(data={"summary": "Dev", "skills": {"backend": ["Python"]}}, raw_text="cv")
    db.add(profile)
    db.commit()

    loaded = db.get(Profile, profile.id)
    assert loaded.data["skills"]["backend"] == ["Python"]
    assert loaded.version == 1
    assert loaded.updated_at is not None


def test_job_with_application_and_status_history(db) -> None:
    job = Job(company="Acme", title="Backend Dev", raw_text="vaga...", extracted={"required": ["Python"]})
    app_ = Application(job=job)
    app_.set_status(ApplicationStatus.SAVED)
    db.add(job)
    db.commit()

    app_.set_status(ApplicationStatus.APPLIED)
    db.commit()

    loaded = db.get(Job, job.id)
    assert loaded.application.status == ApplicationStatus.APPLIED
    assert [h["status"] for h in loaded.application.status_history] == ["saved", "applied"]
    assert loaded.url is None


def test_analysis_and_generated_text_belong_to_job(db) -> None:
    job = Job(company="Acme", title="Dev", raw_text="vaga")
    job.analyses.append(Analysis(profile_version=1, result={"score": 80}))
    job.generated_texts.append(GeneratedText(type=TextType.ANSWER, question="Por quê?", text="..."))
    db.add(job)
    db.commit()

    loaded = db.get(Job, job.id)
    assert loaded.analyses[0].result["score"] == 80
    assert loaded.generated_texts[0].type == TextType.ANSWER


def test_deleting_job_cascades(db) -> None:
    job = Job(company="Acme", title="Dev", raw_text="vaga", application=Application())
    job.analyses.append(Analysis(profile_version=1, result={}))
    db.add(job)
    db.commit()

    db.delete(job)
    db.commit()
    assert db.query(Application).count() == 0
    assert db.query(Analysis).count() == 0
