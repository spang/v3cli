import anthropic
import click
import json
import openai
import tiktoken
import os
import re
import email
import functools
import time

from strip_tags import strip_tags

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo-16k"
OPENAI_TOKEN_LIMIT = 16385

# optional, so don't error out if this doesn't exist
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)

JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "flight_details": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "flight_number": {"type": "string"},
                    "class": {"type": "string"},
                    "departure_datetime": {
                        "type": "string",
                        "pattern": "^[A-Za-z]{3}, [A-Za-z]{3} \\d{2}, \\d{4} \\d{2}:\\d{2} [AP]M$",
                    },
                    "arrival_datetime": {
                        "type": "string",
                        "pattern": "^[A-Za-z]{3}, [A-Za-z]{3} \\d{2}, \\d{4} \\d{2}:\\d{2} [AP]M$",
                    },
                    "departure_city": {
                        "type": "string",
                        "pattern": "^[A-Za-z ]+,[ ]?[A-Z]{2},[ ]?[A-Z]{2}$",
                    },
                    "departure_city_airport_code": {
                        "type": "string",
                        "pattern": "^[A-Z]{3}$",
                    },
                    "arrival_city": {
                        "type": "string",
                        "pattern": "^[A-Za-z ]+,[ ]?[A-Z]{2},[ ]?[A-Z]{2}$",
                    },
                    "arrival_city_airport_code": {
                        "type": "string",
                        "pattern": "^[A-Z]{3}$",
                    },
                    "operated_by": {"type": "string"},
                },
                "required": [
                    "flight_number",
                    "class",
                    "departure_datetime",
                    "arrival_datetime",
                    "departure_city",
                    "arrival_city",
                ],
            },
        },
        "passenger_details": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "eticket_number": {"type": "string"},
                    "frequent_flyer": {"type": "string"},
                    "seats": {"type": "string"},
                },
                "required": ["name", "eticket_number", "frequent_flyer", "seats"],
            },
        },
        "purchase_summary": {
            "type": "object",
            "properties": {
                "method_of_payment": {"type": "string"},
                "date_of_purchase": {
                    "type": "string",
                    "pattern": "^[A-Za-z]{3}, [A-Za-z]{3} \\d{2}, \\d{4}$",
                },
                "airfare": {"type": "string"},
                "taxes_and_fees": {"type": "string"},
                "total_per_passenger": {"type": "string"},
                "total": {"type": "string"},
            },
            "required": [
                "method_of_payment",
                "date_of_purchase",
                "airfare",
                "taxes_and_fees",
                "total_per_passenger",
                "total",
            ],
        },
    },
    "required": ["flight_details", "passenger_details", "purchase_summary"],
}


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


def strip_tags_from_email(email_content):
    stripped = strip_tags(
        email_content,
        minify=True,
        keep_tags=["table", "tr", "td", "head", "div", "br"],
    )

    return stripped


@time_this_function
def extract_flight_details_openai(email_text):
    openai.api_key = OPENAI_API_KEY

    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        functions=[{"name": "set_flight_data", "parameters": JSON_SCHEMA}],
        function_call={"name": "set_flight_data"},
        messages=[
            {
                "role": "system",
                "content": "Extract flight details from email and return in JSON format",
            },
            {"role": "user", "content": email_text},
        ],
    )

    if response and response.choices:
        return response.choices[0].message["function_call"]["arguments"]
    else:
        return None


@time_this_function
def extract_flight_details_anthropic(email_text):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.completions.create(
        model="claude-2",
        max_tokens_to_sample=10000,
        prompt=f"Human: Extract flight details from the following email inside <email></email> XML tags and return it in JSON format between <json></json> XML tags.:\n\n<email>{email_text}</email>\n\nAssistant:",
    )

    # I can't figure out how to get Claude to be concise so I'm using XML tags instead
    if response and response.completion:
        text = response.completion
        match = re.search(r"<json>(.*?)</json>", text, re.DOTALL)
        if match:
            return match.group(1)

    return None


def extract_flight_details(email_text, anthropic=False):
    """Return JSON of flight details from email text"""
    use_this_version = email_text

    if anthropic:
        flight_details = extract_flight_details_anthropic(use_this_version)
    else:
        print("Estimated tokens from email: {}".format(count_tokens(email_text)))
        body_only = email_body_only(email_text)
        print(
            "Estimated tokens from email body only: {}".format(count_tokens(body_only))
        )
        stripped_email = strip_tags_from_email(body_only)
        print(
            "Estimated tokens from email with tags stripped: {}".format(
                count_tokens(stripped_email)
            )
        )
        use_this_version = stripped_email

        if count_tokens(use_this_version) > OPENAI_TOKEN_LIMIT:
            print("Token length too long")
            return

        flight_details = extract_flight_details_openai(use_this_version)

    if flight_details:
        return json.loads(flight_details)
    else:
        return {}


@click.command()
@click.option(
    "-e",
    "--email",
    type=click.Path(exists=True),
    help="Path to the input .eml email file",
)
@click.option(
    "-a",
    "--anthropic",
    is_flag=True,
    default=False,
    help="Use Anthropic to parse instead of OpenAI",
)
def main(email, anthropic):
    try:
        with open(email, "r", encoding="utf-8") as email_file:
            email_text = email_file.read()

        flight_details_json = extract_flight_details(email_text, anthropic)
        if flight_details_json:
            print(json.dumps(flight_details_json, indent=4))
        else:
            print("No flight details found")

    except FileNotFoundError:
        print(f"File not found: {email}")


if __name__ == "__main__":
    main()
