APPLICATION_STATUS_TRANSITIONS = {
    "APPLIED": [
        "SHORTLISTED",
        "REJECTED",
    ],

    "SHORTLISTED": [
        "INTERVIEW",
        "REJECTED",
    ],

    "INTERVIEW": [
        "SELECTED",
        "REJECTED",
    ],

    "SELECTED": [],

    "REJECTED": [],
}