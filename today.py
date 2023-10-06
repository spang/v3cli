#!/usr/bin/env python3
import os

import arrow
import click

import nylas as nylasSDK

NYLAS_API_KEY = os.environ.get("NYLAS_API_KEY")
if not NYLAS_API_KEY:
    raise Exception("Please set the NYLAS_API_KEY environment variable")


def timespan_to_human_readable(timespan):
    # Convert UNIX timestamps to arrow objects in the specified timezones
    start_arrow = arrow.get(timespan.start_time).to(timespan.start_timezone)
    end_arrow = arrow.get(timespan.end_time).to(timespan.end_timezone)

    # Convert the arrow objects to your local timezone
    local_tz = arrow.now().tzinfo
    start_local = start_arrow.to(local_tz)
    end_local = end_arrow.to(local_tz)

    # Format the times in a human-readable form
    time_format = "h:mmA"
    start_str = start_local.format(time_format)
    end_str = end_local.format(time_format)
    time_str = f"{start_str}-{end_str}"

    return time_str


@click.command()
@click.option("--grant-id", "-g", default="me", help="Grant ID")
def today(grant_id):
    """Display all the events I have today"""
    nylas = nylasSDK.Client(api_key=NYLAS_API_KEY)

    today = arrow.now()

    # Get midnight today in the local timezone
    midnight_today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight_today_unix_timestamp = int(midnight_today.timestamp())

    # Get 11:59 PM tonight in the local timezone
    eleven_fifty_nine_tonight = today.replace(
        hour=23, minute=59, second=0, microsecond=0
    )
    eleven_fifty_nine_tonight_unix_timestamp = int(
        eleven_fifty_nine_tonight.timestamp()
    )

    today_events, request_id, next_cursor = nylas.events.list(
        identifier=grant_id,
        query_params=dict(
            calendar_id="primary",
            start=midnight_today_unix_timestamp,
            end=eleven_fifty_nine_tonight_unix_timestamp,
            order_by="start",
            # gets rid of master recurring events that look like duplicates
            expand_recurring=True,
        ),
    )
    if today_events:
        print("Today's events:")
        for event in today_events:
            print(
                "* {} at {}".format(event.title, timespan_to_human_readable(event.when))
            )


if __name__ == "__main__":
    try:
        today()
    except nylasSDK.models.errors.NylasApiError as e:
        print("Nylas API error: {}".format(e))
