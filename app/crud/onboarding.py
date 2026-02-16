from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import OnboardingAnswer, User


def replace_onboarding_answers(db: Session, user: User, data: dict) -> None:
    db.execute(delete(OnboardingAnswer).where(OnboardingAnswer.user_id == user.id))

    rows: list[OnboardingAnswer] = []

    habits = data.get("habits", [])
    habit_answers = data.get("habit_answers", {})
    for habit in habits:
        answers = habit_answers.get(habit, [])
        for idx, ans in enumerate(answers, start=1):
            rows.append(
                OnboardingAnswer(
                    user_id=user.id,
                    module="habits",
                    item_key=habit,
                    question=f"analysis_q{idx}",
                    answer=ans,
                )
            )

    rows.append(
        OnboardingAnswer(
            user_id=user.id,
            module="sports",
            item_key="selected",
            question="selected_sports",
            answer=", ".join(data.get("sports", [])),
        )
    )
    rows.append(
        OnboardingAnswer(
            user_id=user.id,
            module="sports",
            item_key="days",
            question="sport_days",
            answer=data.get("sport_days", ""),
        )
    )
    rows.append(
        OnboardingAnswer(
            user_id=user.id,
            module="reading",
            item_key="book",
            question="selected_book",
            answer=data.get("book", ""),
        )
    )
    rows.append(
        OnboardingAnswer(
            user_id=user.id,
            module="reading",
            item_key="task",
            question="daily_task",
            answer=data.get("reading_task", ""),
        )
    )
    rows.append(
        OnboardingAnswer(
            user_id=user.id,
            module="challenges",
            item_key="picked",
            question="picked_numbers",
            answer=", ".join([str(x) for x in data.get("challenges", [])]),
        )
    )

    for row in rows:
        db.add(row)
    db.commit()
