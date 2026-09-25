from django.template.loader import render_to_string


def render_email_template(
    template_name,
    context,
):
    return render_to_string(
        f"emails/{template_name}.txt",
        context,
    )