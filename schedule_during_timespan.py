#!/usr/bin/env python3
import os

from dateutil import tz

import click
import arrow

import nylas as nylasSDK

# note: this env var can be an app api key OR an access token
NYLAS_API_KEY = os.environ.get("NYLAS_API_KEY")
if not NYLAS_API_KEY:
    raise Exception("Please set the NYLAS_API_KEY environment variable")

nylas = nylasSDK.Client(api_key=NYLAS_API_KEY)


def unix_to_friendly_datetime(unix_timestamp):
    dt = arrow.get(unix_timestamp).to("local")
    friendly_datetime = dt.format("on MMMM D[th] h:mma")
    return friendly_datetime


def find_available_slot(api_response, duration, start_time, end_time):
    # Extract the busy times for each calendar
    busy_times_1 = api_response["data"][0]["time_slots"]
    busy_times_2 = api_response["data"][1]["time_slots"]

    # Initialize pointers to the start of each list of busy times
    pointer_1 = 0
    pointer_2 = 0

    # While there are more busy times to check in both lists
    while pointer_1 < len(busy_times_1) and pointer_2 < len(busy_times_2):
        # Get the current busy time intervals
        busy_time_1 = busy_times_1[pointer_1]
        busy_time_2 = busy_times_2[pointer_2]

        # Find the latest start time and earliest end time of the two busy intervals
        latest_start = max(busy_time_1["end_time"], busy_time_2["end_time"])
        earliest_end = min(
            busy_times_1[pointer_1 + 1]["start_time"]
            if pointer_1 + 1 < len(busy_times_1)
            else end_time,
            busy_times_2[pointer_2 + 1]["start_time"]
            if pointer_2 + 1 < len(busy_times_2)
            else end_time,
        )

        # Check if there is a gap between the busy intervals that is long enough for the meeting
        if (earliest_end - latest_start) >= (
            duration * 60
        ):  # Convert duration to seconds
            return latest_start  # Return the start time of the available slot

        # Move the pointer that points to the earlier ending busy time
        if busy_time_1["end_time"] < busy_time_2["end_time"]:
            pointer_1 += 1
        else:
            pointer_2 += 1

    # If no available slot is found
    return None


def schedule_event_during_availability(
    guest_email, me_email, title, description, start, end, duration, notify
):
    """Schedule an individual event with the given email's calendar"""
    freebusy_response, request_id = nylas.calendars.get_free_busy(
        identifier="me",
        request_body=dict(
            emails=[me_email, guest_email],
            start_time=start,
            end_time=end,
        ),
    )

    errors = [elt for elt in freebusy_response["data"] if elt["object"] == "error"]
    if errors:
        for error in errors:
            print(
                "Error fetching availability for {}: {}".format(
                    error["email"], error["error"]
                )
            )
        return

    print("Call successful")
    print(freebusy_response)

    earliest_time_slot = find_available_slot(freebusy_response, duration, start, end)

    if earliest_time_slot is None:
        print("Couldn't find mutual availability with {}".format(guest_email))
        return

    create_response, request_id = nylas.events.create(
        identifier="me",
        request_body=dict(
            title=title,
            description=description,
            when={
                "start_time": earliest_time_slot,
                "end_time": earliest_time_slot + duration * 60,
            },
            participants=[{"email": guest_email}, {"email": me_email, "status": "yes"}],
        ),
        query_params=dict(
            calendar_id="primary",
            notify_participants=notify,
        ),
    )
    print(
        "Scheduled {}m event with {} starting {}".format(
            duration, guest_email, unix_to_friendly_datetime(earliest_time_slot)
        )
    )


@click.command()
@click.option("--email", "-e", multiple=True, help="Email address of guest")
@click.option("--title", "-t", required=True, help="Title of event")
@click.option("--description", "-d", help="Description of event")
@click.option("--start", "-s", help="Start date of availability search")
@click.option("--end", help="End date of availability search")
@click.option(
    "--notify/--no-notify", default=True, help="Whether to notify participants"
)
@click.option(
    "--duration", default=30, type=int, help="How long the meeting will be in minutes"
)
def main(email, title, description, start, end, duration, notify):
    """For each guest specified, schedule a meeting between the guest and
    the authorized user with the given title and description. Event will
    occur during an available time block within the given start and end"""

    grant_metadata, request_id = nylas.auth.grants.find("me")

    local_tz = tz.tzlocal()
    start_unix_timestamp = int(arrow.get(start, tzinfo=local_tz).timestamp())
    end_unix_timestamp = int(arrow.get(end, tzinfo=local_tz).timestamp())

    print("Will check availability for the following emails: {}".format(email))

    for eml in email:
        schedule_event_during_availability(
            eml,
            grant_metadata.email,
            title,
            description,
            start_unix_timestamp,
            end_unix_timestamp,
            duration,
            notify,
        )


if __name__ == "__main__":
    try:
        main()
    except nylasSDK.models.errors.NylasApiError as e:
        print("Nylas API error: {}".format(e))
