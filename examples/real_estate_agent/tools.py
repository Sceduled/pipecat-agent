"""
Real Estate Agent — LLM tool functions.

Every function must follow the Pipecat convention:
  - First argument is `params: FunctionCallParams`
  - Remaining arguments are the tool's parameters (with type hints)
  - Google-style docstring — the Args section generates the JSON schema
  - Call `await params.result_callback(dict)` to return the result to the LLM
"""

import uuid
from datetime import datetime

from loguru import logger

from pipecat.services.llm_service import FunctionCallParams

# ---------------------------------------------------------------------------
# Mock data — replace these with real DB / CRM calls
# ---------------------------------------------------------------------------

PROPERTY_DB = [
    {
        "id": "PRES-WF-001",
        "name": "Prestige Lakeside Habitat",
        "location": "Whitefield",
        "city": "Bangalore",
        "bhk": 3,
        "price_lakhs": 85,
        "rent_per_month": None,
        "purpose": ["buy"],
        "possession": "Dec 2026",
        "highlights": "Clubhouse, pool, 24x7 security, 2 km from ITPL",
        "rera": "PRM/KA/RERA/1251/309/PR/200515/002641",
    },
    {
        "id": "PRES-WF-002",
        "name": "Prestige Tech Vista",
        "location": "Whitefield",
        "city": "Bangalore",
        "bhk": 2,
        "price_lakhs": 62,
        "rent_per_month": None,
        "purpose": ["buy", "invest"],
        "possession": "Ready to move",
        "highlights": "Gym, co-working space, metro nearby, 5 year rental guarantee option",
        "rera": "PRM/KA/RERA/1251/309/PR/210302/004512",
    },
    {
        "id": "PRES-MG-001",
        "name": "Prestige Meridian Park",
        "location": "MG Road",
        "city": "Bangalore",
        "bhk": 3,
        "price_lakhs": 145,
        "rent_per_month": None,
        "purpose": ["buy"],
        "possession": "June 2027",
        "highlights": "Sky lounge, concierge, premium fittings, central location",
        "rera": "PRM/KA/RERA/1251/309/PR/220118/006723",
    },
    {
        "id": "PRES-EC-001",
        "name": "Prestige Green Fields",
        "location": "Electronic City",
        "city": "Bangalore",
        "bhk": 2,
        "price_lakhs": 48,
        "rent_per_month": 22000,
        "purpose": ["buy", "rent", "invest"],
        "possession": "Ready to move",
        "highlights": "Close to Infosys/Wipro campuses, good rental yield, gated community",
        "rera": "PRM/KA/RERA/1251/309/PR/190820/003241",
    },
]


# ---------------------------------------------------------------------------
# Shared tools (used by both inbound and outbound agents)
# ---------------------------------------------------------------------------


async def search_properties(
    params: FunctionCallParams,
    location: str,
    bhk: int,
    budget_max_lakhs: float,
    purpose: str,
) -> None:
    """Search available properties matching the caller's requirements.

    Args:
        location: Area or locality name, e.g. Whitefield, MG Road, Electronic City.
        bhk: Number of bedrooms required. Use 0 if not specified.
        budget_max_lakhs: Maximum budget in lakhs INR. Use 0 if not specified.
        purpose: Purpose of property — buy, rent, or invest.
    """
    results = []
    for prop in PROPERTY_DB:
        location_match = location.lower() in prop["location"].lower() or location.lower() in prop["city"].lower()
        purpose_match = purpose.lower() in prop["purpose"]
        bhk_match = bhk == 0 or prop["bhk"] == bhk
        budget_match = budget_max_lakhs == 0 or prop["price_lakhs"] <= budget_max_lakhs

        if location_match and purpose_match and bhk_match and budget_match:
            results.append({
                "id": prop["id"],
                "name": prop["name"],
                "bhk": prop["bhk"],
                "price_lakhs": prop["price_lakhs"],
                "possession": prop["possession"],
                "highlights": prop["highlights"],
            })

    if not results:
        await params.result_callback({
            "found": 0,
            "message": "No exact match found. Try relaxing budget or location.",
        })
    else:
        await params.result_callback({"found": len(results), "properties": results})


async def get_property_details(params: FunctionCallParams, property_id: str) -> None:
    """Get full details of a specific property by its ID.

    Args:
        property_id: The property ID, e.g. PRES-WF-001.
    """
    prop = next((p for p in PROPERTY_DB if p["id"] == property_id), None)
    if prop:
        await params.result_callback(prop)
    else:
        await params.result_callback({"error": f"Property {property_id} not found."})


async def calculate_emi(
    params: FunctionCallParams,
    price_lakhs: float,
    down_payment_percent: float,
    interest_rate: float,
    tenure_years: int,
) -> None:
    """Calculate monthly home loan EMI for a property.

    Args:
        price_lakhs: Total property price in lakhs INR.
        down_payment_percent: Down payment as percentage of price, e.g. 20 for 20%.
        interest_rate: Annual interest rate percentage, e.g. 8.5.
        tenure_years: Loan tenure in years, e.g. 20.
    """
    price = price_lakhs * 100_000
    principal = price * (1 - down_payment_percent / 100)
    monthly_rate = interest_rate / 100 / 12
    months = tenure_years * 12

    if monthly_rate == 0:
        emi = principal / months
    else:
        emi = principal * monthly_rate * (1 + monthly_rate) ** months / ((1 + monthly_rate) ** months - 1)

    await params.result_callback({
        "property_price_lakhs": price_lakhs,
        "down_payment_lakhs": round(price * (down_payment_percent / 100) / 100_000, 2),
        "loan_amount_lakhs": round(principal / 100_000, 2),
        "emi_per_month_rupees": round(emi),
        "total_interest_lakhs": round((emi * months - principal) / 100_000, 2),
        "total_outflow_lakhs": round(emi * months / 100_000, 2),
    })


async def book_site_visit(
    params: FunctionCallParams,
    caller_name: str,
    caller_phone: str,
    property_id: str,
    preferred_date: str,
    preferred_time: str,
) -> None:
    """Book a property site visit for the caller.

    Args:
        caller_name: Full name of the caller.
        caller_phone: Caller's phone number with country code.
        property_id: Property ID to visit, e.g. PRES-WF-001.
        preferred_date: Preferred visit date in YYYY-MM-DD format.
        preferred_time: Preferred visit time, e.g. 10:00 AM.
    """
    # TODO: integrate with Google Calendar or your CRM booking system
    logger.info(f"Site visit booked: {caller_name} | {caller_phone} | {property_id} | {preferred_date} {preferred_time}")

    # Format date as spoken English so the LLM doesn't read "2026-06-25" aloud.
    try:
        spoken_date = datetime.strptime(preferred_date, "%Y-%m-%d").strftime("%A the %-d of %B")
    except (ValueError, AttributeError):
        spoken_date = preferred_date

    await params.result_callback({
        "status": "confirmed",
        "property_id": property_id,
        "spoken_date": spoken_date,
        "time": preferred_time,
        "message": f"Visit confirmed for {spoken_date} at {preferred_time}.",
    })


async def save_lead(
    params: FunctionCallParams,
    name: str,
    phone: str,
    budget_max_lakhs: float,
    preferred_location: str,
    bhk: int,
    purpose: str,
    notes: str,
) -> None:
    """Save the caller's details as a lead in CRM.

    Args:
        name: Caller's full name.
        phone: Caller's phone number.
        budget_max_lakhs: Maximum budget in lakhs INR. Use 0 if unknown.
        preferred_location: Preferred area or locality.
        bhk: BHK requirement. Use 0 if not specified.
        purpose: buy, rent, or invest.
        notes: Any additional notes about the caller's requirements.
    """
    # TODO: POST to your CRM — HubSpot, Zoho, Salesforce, etc.
    lead_id = "LEAD-" + datetime.now().strftime("%Y%m%d%H%M%S")
    logger.info(f"Lead saved: {name} | {phone} | {purpose} {bhk}BHK in {preferred_location} | Budget: {budget_max_lakhs}L")

    await params.result_callback({
        "status": "saved",
        "lead_id": lead_id,
        "message": "Lead saved successfully.",
    })


async def transfer_to_agent(params: FunctionCallParams, reason: str) -> None:
    """Transfer the caller to a human sales agent.

    Args:
        reason: Brief reason for transfer, e.g. caller wants to negotiate price.
    """
    logger.info(f"Transferring call to human agent. Reason: {reason}")
    # TODO: trigger call transfer via Vobiz API or your telephony system
    await params.result_callback({
        "status": "transferring",
        "message": "Transfer initiated. Tell the caller warmly that you are connecting them to a colleague right away.",
    })


# ---------------------------------------------------------------------------
# Outbound-only tools
# ---------------------------------------------------------------------------


async def confirm_site_visit(
    params: FunctionCallParams,
    caller_name: str,
    visit_date: str,
    visit_time: str,
    property_name: str,
) -> None:
    """Confirm or update the details of a scheduled site visit.

    Args:
        caller_name: Caller's name.
        visit_date: Scheduled visit date in YYYY-MM-DD format.
        visit_time: Scheduled visit time, e.g. 11:00 AM.
        property_name: Name of the property to be visited.
    """
    try:
        spoken_date = datetime.strptime(visit_date, "%Y-%m-%d").strftime("%A the %-d of %B")
    except (ValueError, AttributeError):
        spoken_date = visit_date

    await params.result_callback({
        "status": "confirmed",
        "spoken_date": spoken_date,
        "time": visit_time,
        "property": property_name,
        "message": f"Visit confirmed for {spoken_date} at {visit_time} for {property_name}.",
    })


async def update_call_outcome(
    params: FunctionCallParams,
    lead_phone: str,
    outcome: str,
    notes: str,
) -> None:
    """Log the result of this outbound call in CRM.

    Args:
        lead_phone: Lead's phone number.
        outcome: Call outcome — interested, not_interested, callback_requested, visit_booked, no_answer.
        notes: Brief notes about the conversation.
    """
    # TODO: update your CRM record
    logger.info(f"Call outcome logged: {lead_phone} | {outcome} | {notes}")
    await params.result_callback({"status": "logged", "outcome": outcome})


# ---------------------------------------------------------------------------
# Tool lists for each agent
# ---------------------------------------------------------------------------

INBOUND_TOOLS = [
    search_properties,
    get_property_details,
    calculate_emi,
    book_site_visit,
    save_lead,
    transfer_to_agent,
]

OUTBOUND_TOOLS = [
    search_properties,
    get_property_details,
    calculate_emi,
    book_site_visit,
    confirm_site_visit,
    save_lead,
    update_call_outcome,
    transfer_to_agent,
]
