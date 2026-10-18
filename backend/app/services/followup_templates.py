"""
Prebuilt follow-up templates, written in a humble, professional tone —
short, no pressure, easy for a recruiter to answer in one line.
Placeholders are filled in from the application/job/user record.
"""

TEMPLATES = {
    "post_application_checkin": {
        "label": "Check-in after applying (no response yet)",
        "subject": "Following up on my application for {job_title}",
        "body": (
            "Hi {company} team,\n\n"
            "I hope you're doing well. I applied for the {job_title} role on {applied_date} "
            "and wanted to check in, as I'm very interested in the opportunity.\n\n"
            "If there's any additional information I can share to help with the review, "
            "please let me know. I understand things can take time and appreciate you "
            "considering my application.\n\n"
            "Thank you for your time.\n\n"
            "Best regards,\n{your_name}"
        ),
    },
    "post_interview_thanks": {
        "label": "Thank-you after an interview",
        "subject": "Thank you for the conversation \u2014 {job_title}",
        "body": (
            "Hi {company} team,\n\n"
            "Thank you for taking the time to speak with me about the {job_title} role. "
            "I enjoyed learning more about the team and the work, and I remain very "
            "interested in the opportunity.\n\n"
            "Please let me know if there's anything further you need from my side. "
            "Looking forward to hearing about next steps whenever convenient for you.\n\n"
            "Best regards,\n{your_name}"
        ),
    },
    "long_silence_nudge": {
        "label": "Gentle nudge after extended silence",
        "subject": "Checking in once more \u2014 {job_title}",
        "body": (
            "Hi {company} team,\n\n"
            "I wanted to follow up one more time on my application for the {job_title} role "
            "submitted on {applied_date}. I completely understand hiring timelines can shift, "
            "and I don't want to be a bother.\n\n"
            "If the role has been filled or is no longer being considered, a quick note either "
            "way would be genuinely appreciated so I can plan accordingly. Otherwise, I remain "
            "very interested and happy to provide anything further that's useful.\n\n"
            "Thank you again for your time and consideration.\n\n"
            "Best regards,\n{your_name}"
        ),
    },
}


def render_template(template_key: str, *, job_title: str, company: str, applied_date: str, your_name: str) -> dict:
    tpl = TEMPLATES.get(template_key, TEMPLATES["post_application_checkin"])
    return {
        "subject": tpl["subject"].format(job_title=job_title, company=company),
        "body": tpl["body"].format(
            job_title=job_title, company=company, applied_date=applied_date, your_name=your_name
        ),
    }
