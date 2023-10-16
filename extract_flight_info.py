import click
import json
import openai
import tiktoken
import os
import email
import functools
import time

from bs4 import BeautifulSoup

# Set your OpenAI API key from the environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo-16k"


def time_this_function(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        print(f"{func.__name__} ran in: {duration:.5f} seconds")
        return result

    return wrapper


def email_body_only(email_text):
    msg = email.message_from_string(email_text)
    body_content = []

    # Walk through all parts of the email
    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = part.get("Content-Disposition")

        # Only consider parts that are not attachments and are in text format
        if not content_disposition or content_disposition.startswith("inline"):
            if content_type == "text/plain" or content_type == "text/html":
                body_content.append(
                    part.get_payload(decode=True).decode(
                        part.get_content_charset(), errors="replace"
                    )
                )

    return "\n\n".join(body_content)


def count_tokens(text):
    enc = tiktoken.encoding_for_model(OPENAI_MODEL)
    return len(enc.encode(text))


def remove_css_from_email(email_content):
    # Parse the email content with BeautifulSoup
    soup = BeautifulSoup(email_content, "html.parser")

    # Find and extract all <style> tags
    for style_tag in soup.find_all("style"):
        style_tag.decompose()

    # Return the processed email content
    return str(soup)


# Function to extract flight details using GPT API
@time_this_function
def extract_flight_details(email_text):
    openai.api_key = OPENAI_API_KEY

    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Extract flight details from email and return in JSON format",
            },
            {"role": "user", "content": email_text},
        ],
    )

    if response and response.choices:
        return response.choices[0].message["content"]
    else:
        return None


@click.command()
@click.option(
    "-e",
    "--email",
    type=click.Path(exists=True),
    help="Path to the input .eml email file",
)
def main(email):
    try:
        with open(email, "r", encoding="utf-8") as email_file:
            email_text = email_file.read()

        print("Estimated tokens from email: {}".format(count_tokens(email_text)))
        css_stripped_email = remove_css_from_email(email_text)
        print(
            "Estimated tokens from email with CSS stripped: {}".format(
                count_tokens(css_stripped_email)
            )
        )
        body_only = email_body_only(email_text)
        print(
            "Estimated tokens from email body only: {}".format(count_tokens(body_only))
        )
        use_this_version = body_only

        if count_tokens(use_this_version) > 16000:
            print("Token length too long")
            return

        flight_details = extract_flight_details(use_this_version)

        if flight_details:
            parsed_data = json.loads(flight_details)
            print(json.dumps(parsed_data, indent=4))
        else:
            print("Failed to extract flight details from the email.")
    except FileNotFoundError:
        print(f"File not found: {email}")


if __name__ == "__main__":
    main()
