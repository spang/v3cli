#!/usr/bin/env python3
import os

import click

import nylas as nylasSDK

NYLAS_API_KEY = os.environ.get("NYLAS_API_KEY")
if not NYLAS_API_KEY:
    raise Exception("Please set the NYLAS_API_KEY environment variable")


def user_inputs_y(message):
    choice = input("{message} (y/n): ".format(message=message))
    return choice.lower() == "y"


@click.command()
@click.option("--grant-id", "-g", default="me", help="Grant ID")
@click.option("--yes", "-y", help="skip prompting")
@click.option(
    "--notify/--no-notify", default=True, help="Whether to notify participants"
)
def delete_test_events(grant_id, yes, notify):
    """Delete all events on the primary calendar matching the title 'test event'"""
    nylas = nylasSDK.Client(api_key=NYLAS_API_KEY)

    test_events, request_id, next_cursor = nylas.events.list(
        identifier=grant_id,
        query_params=dict(
            calendar_id="primary",
            title="test event",
        ),
    )
    print("Found {} events".format(len(test_events)))
    if test_events:
        if yes or user_inputs_y("Do you want to delete these events?"):
            for event in test_events:
                print("* Deleting event with ID {}".format(event.id))
                nylas.events.destroy(
                    grant_id,
                    event.id,
                    dict(calendar_id="primary", notify_participants=notify),
                )


if __name__ == "__main__":
    try:
        delete_test_events()
    except nylasSDK.models.errors.NylasApiError as e:
        print("Nylas API error: {}".format(e))
