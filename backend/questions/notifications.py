import logging

from django.core.mail import send_mail
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

# Final score (average of the approved scores) from which the person is congratulated.
RECOGNITION_SCORE = 4.0


def notify_review(person, average):
    """Emails the final score once the boss approves a submission.

    4.0 or higher: congratulations. Lower: an encouraging message.
    """
    if not person.email:
        return
    params = {"name": person.first_name, "average": average}
    if average >= RECOGNITION_SCORE:
        subject = _("Congratulations! Your evaluation result - Heroes del Corazon")
        body = _(
            "Congratulations, %(name)s!\n\n"
            "Your evaluation was reviewed and your final score is %(average)s out of 5. "
            "Your work and commitment make you one of the heroes of our institution. "
            "Thank you for everything you give to the team!"
        )
    else:
        subject = _("Your evaluation result - Heroes del Corazon")
        body = _(
            "Hello %(name)s,\n\n"
            "Your evaluation was reviewed and your current final score is %(average)s out of 5. "
            "Thank you for your effort: every step counts and we are sure you can reach your goals. "
            "Keep going, we are with you next month!"
        )

    # Failures are only logged (see except below): an SMTP outage must not make the submission fail.
    # views.py calls this from transaction.on_commit, so nothing is sent for a rolled-back submission.
    message = body % params + "\n\n" + _("Heroes del Corazon team")
    try:
        send_mail(subject=subject, message=message, from_email=None, recipient_list=[person.email])
    except Exception:
        logger.exception("Could not send the review notification")
