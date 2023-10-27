#!/usr/bin/env python3
import os
import json

import click

from dateutil import parser

import nylas as nylasSDK

from extract_flight_info import extract_flight_details

NYLAS_API_KEY = os.environ.get("NYLAS_API_KEY")
if not NYLAS_API_KEY:
    raise Exception("Please set the NYLAS_API_KEY environment variable")


import logging
import requests

# Set up logging to print out HTTP request information
logging.basicConfig(level=logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


@click.command()
# a click option --from-emails that accepts multiple values of email strings
@click.option(
    "--from-emails",
    multiple=True,
    required=True,
    help="Emails to extract flight details from",
)
@click.option(
    "--read-from-cache",
    is_flag=True,
    default=False,
    help="Read email details from cache instead of calling OpenAI API",
)
@click.option("--grant-id", "-g", default="me", help="Grant ID")
def main(from_emails, grant_id, read_from_cache):
    """Schedule calendar events corresponding to the flight details on the grant's primary calendar"""
    nylas = nylasSDK.Client(api_key=NYLAS_API_KEY)

    messages, request_id, next_cursor = nylas.messages.list(
        identifier=grant_id,
        query_params=dict(
            any_email=from_emails,
        ),
    )

    for message in messages:
        print("Message: {} {}".format(message.date, message.subject))


if __name__ == "__main__":
    try:
        main()
    except nylasSDK.models.errors.NylasApiError as e:
        print("Nylas API error: {} {}".format(e.status_code, e))
        if e.provider_error:
            print("Provider error: {}".format(e.provider_error))
