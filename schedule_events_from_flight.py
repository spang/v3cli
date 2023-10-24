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


@click.command()
@click.option(
    "-e",
    "--email",
    type=click.Path(exists=True),
    help="Path to the input .eml email file",
)
@click.option(
    "--read-from-cache",
    is_flag=True,
    default=False,
    help="Read email details from cache instead of calling OpenAI API",
)
@click.option("--grant-id", "-g", default="me", help="Grant ID")
def main(email, grant_id, read_from_cache):
    """Schedule calendar events corresponding to the flight details on the grant's primary calendar"""
    with open(email, "r", encoding="utf-8") as email_file:
        email_text = email_file.read()

    nylas = nylasSDK.Client(api_key=NYLAS_API_KEY)

    if read_from_cache:
        with open("flight_details.json", "r") as f:
            flight_details = json.loads(f.read())
    else:
        flight_details = extract_flight_details(email_text)

    # write the extracted json to a file to ease debugging
    with open("flight_details.json", "w") as f:
        f.write(json.dumps(flight_details, indent=4))

    # step 1: we just wanna put calendar events for the flight itself on the calendar
    # later we'll also add an all-day event with the trip name too
    # the contents of flight_details is a dict that looks like this:
    # {
    # "flight_details": [
    #     {
    #         "flight_number": "UA 1850",
    #         "class": "United Economy (H)",
    #         "departure_datetime": "Wed, Nov 08, 2023 11:10 AM",
    #         "arrival_datetime": "Wed, Nov 08, 2023 07:48 PM",
    #         "departure_city": "San Francisco, CA",
    #         "departure_city_airport_code": "SFO",
    #         "arrival_city": "New York/Newark, NJ",
    #         "arrival_city_airport_code": "EWR",
    #         "operated_by": "United Airlines"
    #     },
    #     ]
    # }

    # write the code that uses nylas.events.create and the above details to create
    # events for each flight
    # convert the departure_datetime and arrival_datetime to unix timestamps using arrow library

    for flight in flight_details["flight_details"]:
        print(
            "processing flight {} departing {} from {}".format(
                flight["flight_number"],
                flight["departure_datetime"],
                flight["departure_city"],
            )
        )
        start_unix_timestamp = int(
            parser.parse(flight["departure_datetime"]).timestamp()
        )
        end_unix_timestamp = int(parser.parse(flight["arrival_datetime"]).timestamp())

        description = json.dumps(flight, indent=4)

        event, request_id = nylas.events.create(
            identifier=grant_id,
            request_body=dict(
                title="Flight {} {}->{}".format(
                    flight["flight_number"],
                    flight["departure_city_airport_code"],
                    flight["arrival_city_airport_code"],
                ),
                description=description,
                when={
                    "start_time": start_unix_timestamp,
                    "end_time": end_unix_timestamp,
                },
            ),
            query_params=dict(
                calendar_id="primary",
            ),
        )
        print("Event created with ID: {}".format(event.id))


if __name__ == "__main__":
    try:
        main()
    except nylasSDK.models.errors.NylasApiError as e:
        print("Nylas API error: {}".format(e))
