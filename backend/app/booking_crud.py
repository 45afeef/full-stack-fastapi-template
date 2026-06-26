from collections import defaultdict

from sqlalchemy.orm import selectinload, load_only

from app.models.travel.booking import Booking, BookingCab, BookingStay, BookingTraveller
from app.models.travel.cab import Cab, Driver
from app.models.travel.providers import CabServiceProvider, ServiceProvider, StayServiceProvider
from app.models.travel.stay import StayUnit
from app.models.user.profile import Profile


# =========================================================
# LOADER
# =========================================================

def booking_details_loader(stmt):

    return stmt.options(

        # =================================================
        # BOOKING
        # =================================================
        load_only(
            Booking.id,
            Booking.date_starting_from,
            Booking.date_ending_on,
            Booking.status,
            Booking.total_amount,
        ),

        # =================================================
        # TRAVELLERS
        # =================================================
        selectinload(Booking.travellers)
        .load_only(
            BookingTraveller.id,
            BookingTraveller.traveller_id,
        )
        .selectinload(BookingTraveller.traveller)
        .load_only(
            Profile.id,
            Profile.first_name,
            Profile.last_name,
            Profile.primary_phone_number,
            Profile.primary_email,
        ),

        # =================================================
        # CABS
        # =================================================
        selectinload(Booking.cabs)
        .load_only(
            BookingCab.id,
            BookingCab.pickup_time,
            BookingCab.pickup_location,
            BookingCab.drop_time,
            BookingCab.drop_location,
            BookingCab.rate,
            BookingCab.status,
            BookingCab.cab_provider_id,
        ),

        # CAB
        selectinload(Booking.cabs)
        .selectinload(BookingCab.cab)
        .load_only(
            Cab.id,
            Cab.name,
            Cab.vehicle_number,
            Cab.vehicle_type,
            Cab.capacity,
            Cab.color,
            Cab.company_model
        ),

        # DRIVER
        selectinload(Booking.cabs)
        .selectinload(BookingCab.driver)
        .load_only(
            Driver.id,
            Driver.profile_id,
        ),

        # DRIVER PROFILE
        selectinload(Booking.cabs)
        .selectinload(BookingCab.driver)
        .selectinload(Driver.profile)
        .load_only(
            Profile.id,
            Profile.first_name,
            Profile.last_name,
            Profile.primary_phone_number,
        ),

        # CAB PROVIDER
        selectinload(Booking.cabs)
        .selectinload(BookingCab.cab_provider)
        .selectinload(CabServiceProvider.provider)
        .load_only(
            ServiceProvider.id,
            ServiceProvider.provider_name,
        ),

        # =================================================
        # STAYS
        # =================================================
        selectinload(Booking.stays)
        .load_only(
            BookingStay.id,
            BookingStay.check_in,
            BookingStay.check_out,
            BookingStay.room_type,
            BookingStay.rate,
            BookingStay.status,
            BookingStay.stay_provider_id,
        ),

        # STAY UNIT
        selectinload(Booking.stays)
        .selectinload(BookingStay.stayunit)
        .load_only(
            StayUnit.id,
            StayUnit.name,
            StayUnit.room_rate,
            StayUnit.max_occupancy,
        ),

        # STAY PROVIDER
        selectinload(Booking.stays)
        .selectinload(BookingStay.stay_provider)
        .selectinload(StayServiceProvider.provider)
        .load_only(
            ServiceProvider.id,
            ServiceProvider.provider_name,
        ),
    )


# =========================================================
# MAIN SERIALIZER
# =========================================================

def serialize_booking(booking: Booking):

    cab_provider_map = defaultdict(list)
    stay_provider_map = defaultdict(list)

    # =================================================
    # GROUP CABS
    # =================================================

    for item in booking.cabs:

        provider = None

        if (
            item.cab_provider
            and item.cab_provider.provider
        ):
            provider = item.cab_provider.provider

        provider_key = str(provider.id) if provider else "unknown"

        cab_provider_map[provider_key].append({
            "provider": provider,
            "cab": serialize_booking_cab(item),
        })

    # =================================================
    # GROUP STAYS
    # =================================================

    for item in booking.stays:

        provider = None

        if (
            item.stay_provider
            and item.stay_provider.provider
        ):
            provider = item.stay_provider.provider

        provider_key = str(provider.id) if provider else "unknown"

        stay_provider_map[provider_key].append({
            "provider": provider,
            "stay": serialize_booking_stay(item),
        })

    # =================================================
    # RESPONSE
    # =================================================

    return {
        "id": booking.id,
        "date_starting_from": booking.date_starting_from,
        "date_ending_on": booking.date_ending_on,
        "status": booking.status,
        "total_amount": booking.total_amount,

        # =================================================
        # TRAVELLERS
        # =================================================
        "travellers": [
            {
                "id": t.traveller.id,
                "first_name": t.traveller.first_name,
                "last_name": t.traveller.last_name,
                "phone": t.traveller.primary_phone_number,
                "email": t.traveller.primary_email,
            }
            for t in booking.travellers
            if t.traveller
        ],

        # =================================================
        # CAB PROVIDERS
        # =================================================
        "cab_providers": [
            {
                "id": items[0]["provider"].id,
                "name": items[0]["provider"].provider_name,

                "cabs": [
                    item["cab"]
                    for item in items
                ]
            }
            for _, items in cab_provider_map.items()
            if items[0]["provider"]
        ],

        # =================================================
        # STAY PROVIDERS
        # =================================================
        "stay_providers": [
            {
                "id": items[0]["provider"].id,
                "name": items[0]["provider"].provider_name,

                "stays": [
                    item["stay"]
                    for item in items
                ]
            }
            for _, items in stay_provider_map.items()
            if items[0]["provider"]
        ],
    }


# =========================================================
# CAB SERIALIZER
# =========================================================

def serialize_booking_cab(item: BookingCab):

    cab = item.cab
    driver = item.driver

    return {
        "id": item.id,

        "pickup_time": item.pickup_time,
        "pickup_location": item.pickup_location,

        "drop_time": item.drop_time,
        "drop_location": item.drop_location,

        "rate": item.rate,
        "status": item.status,

        # =================================================
        # CAB
        # =================================================
        "cab": (
            {
                "id": cab.id,
                "name": cab.name,
                "vehicle_number": cab.vehicle_number,
                "vehicle_type": cab.vehicle_type,
                "capacity": cab.capacity,
                "color": cab.color,
                "model": cab.company_model,
            }
            if cab
            else None
        ),

        # =================================================
        # DRIVER
        # =================================================
        "driver": (
            {
                "id": driver.id,
                "first_name": driver.profile.first_name,
                "last_name": driver.profile.last_name,
                "phone": driver.profile.primary_phone_number,
            }
            if driver and driver.profile
            else None
        ),
    }


# =========================================================
# STAY SERIALIZER
# =========================================================

def serialize_booking_stay(item: BookingStay):

    unit = item.stayunit

    return {
        "id": item.id,

        "check_in": item.check_in,
        "check_out": item.check_out,

        "room_type": item.room_type,
        "rate": item.rate,
        "status": item.status,

        # =================================================
        # UNIT
        # =================================================
        "unit": (
            {
                "id": unit.id,
                "name": unit.name,
                "room_rate": unit.room_rate,
                "max_occupancy": unit.max_occupancy,
            }
            if unit
            else None
        ),
    }