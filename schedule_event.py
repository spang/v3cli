#!/usr/bin/env python3
import os
from datetime import datetime

import click
from dateutil import parser

import nylas as nylasSDK

NYLAS_API_KEY = os.environ.get("NYLAS_API_KEY")
if not NYLAS_API_KEY:
    raise Exception("Please set the NYLAS_API_KEY environment variable")

# parse up to 10 email addresses using click
@click.command()
@click.option("--email", "-e", multiple=True, help="Email address of guest")
@click.option("--title", "-t", help="Title of event")
@click.option("--description", "-d", help="Description of event")
# parse start date using click
@click.option("--start", "-s", help="Start date of event")
# end date too
@click.option("--end", help="End date of event")
# click parse option to pass in grant ID
@click.option("--grant-id", "-g", help="Grant ID")
def schedule_event(email, title, description, start, end, grant_id):
    """Schedule an event with Nylas"""
    nylas = nylasSDK.Client(api_key=NYLAS_API_KEY)

    start_unix_timestamp = int(parser.parse(start).timestamp())
    end_unix_timestamp = int(parser.parse(end).timestamp())

    # create the event on the primary calendar
    event, _ = nylas.events.create(
        identifier=grant_id,
        request_body=dict(
            calendar_id="primary",
            title=title,
            description=description,
            when={"start_time": start_unix_timestamp, "end_time": end_unix_timestamp},
        ),
        query_params=dict(
            calendar_id=primary_calendar.id,
            notify_participants=True,
        ),
    )
    print("Event created with ID: {}".format(event.id))


if __name__ == "__main__":
    try:
        schedule_event()
    except nylasSDK.models.errors.NylasApiError as e:
        print("Nylas API error: {}".format(e))
