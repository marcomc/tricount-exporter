from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def sample_api_response() -> dict:
    return {
        "Response": [
            {
                "Registry": {
                    "title": "City trip",
                    "memberships": [
                        {"RegistryMembershipNonUser": {"alias": {"display_name": "Marco"}}},
                        {"RegistryMembershipNonUser": {"alias": {"display_name": "Giulia"}}},
                    ],
                    "all_registry_entry": [
                        {
                            "RegistryEntry": {
                                "type_transaction": "NORMAL",
                                "membership_owned": {
                                    "RegistryMembershipNonUser": {
                                        "alias": {"display_name": "Marco"}
                                    }
                                },
                                "amount": {"value": "-24.50", "currency": "EUR"},
                                "description": "Dinner",
                                "date": "2026-04-09 18:30:00.000000",
                                "allocations": [
                                    {
                                        "membership": {
                                            "RegistryMembershipNonUser": {
                                                "alias": {"display_name": "Marco"}
                                            }
                                        },
                                        "amount": {"value": "-12.25"},
                                    },
                                    {
                                        "membership": {
                                            "RegistryMembershipNonUser": {
                                                "alias": {"display_name": "Giulia"}
                                            }
                                        },
                                        "amount": {"value": "-12.25"},
                                    },
                                ],
                                "category": "FOOD",
                                "attachment": [
                                    {"urls": [{"url": "https://example.invalid/receipt-1.jpg"}]}
                                ],
                            }
                        }
                    ],
                }
            }
        ]
    }


@pytest.fixture()
def sample_api_response_two_transactions() -> dict:
    return {
        "Response": [
            {
                "Registry": {
                    "title": "City trip",
                    "memberships": [
                        {"RegistryMembershipNonUser": {"alias": {"display_name": "Marco"}}},
                        {"RegistryMembershipNonUser": {"alias": {"display_name": "Giulia"}}},
                    ],
                    "all_registry_entry": [
                        {
                            "RegistryEntry": {
                                "type_transaction": "NORMAL",
                                "membership_owned": {
                                    "RegistryMembershipNonUser": {
                                        "alias": {"display_name": "Marco"}
                                    }
                                },
                                "amount": {"value": "-24.50", "currency": "EUR"},
                                "description": "Dinner",
                                "date": "2026-04-09 18:30:00.000000",
                                "allocations": [
                                    {
                                        "membership": {
                                            "RegistryMembershipNonUser": {
                                                "alias": {"display_name": "Marco"}
                                            }
                                        },
                                        "amount": {"value": "-12.25"},
                                    },
                                    {
                                        "membership": {
                                            "RegistryMembershipNonUser": {
                                                "alias": {"display_name": "Giulia"}
                                            }
                                        },
                                        "amount": {"value": "-12.25"},
                                    },
                                ],
                                "category": "FOOD",
                                "attachment": [
                                    {"urls": [{"url": "https://example.invalid/receipt-1.jpg"}]}
                                ],
                            }
                        },
                        {
                            "RegistryEntry": {
                                "type_transaction": "NORMAL",
                                "membership_owned": {
                                    "RegistryMembershipNonUser": {
                                        "alias": {"display_name": "Giulia"}
                                    }
                                },
                                "amount": {"value": "-12.00", "currency": "EUR"},
                                "description": "Museum",
                                "date": "2026-04-15 12:00:00.000000",
                                "allocations": [
                                    {
                                        "membership": {
                                            "RegistryMembershipNonUser": {
                                                "alias": {"display_name": "Marco"}
                                            }
                                        },
                                        "amount": {"value": "-6.00"},
                                    },
                                    {
                                        "membership": {
                                            "RegistryMembershipNonUser": {
                                                "alias": {"display_name": "Giulia"}
                                            }
                                        },
                                        "amount": {"value": "-6.00"},
                                    },
                                ],
                                "category": "ACTIVITIES",
                                "attachment": [],
                            }
                        },
                    ],
                }
            }
        ]
    }


@pytest.fixture()
def sample_rich_api_response(sample_api_response: dict) -> dict:
    transaction = sample_api_response["Response"][0]["Registry"]["all_registry_entry"][0][
        "RegistryEntry"
    ]
    transaction.update(
        {
            "id": 123456789,
            "uuid": "9c18864f-0e6d-413d-aad7-592d0b99d237",
            "created": "2026-04-09 18:20:00.000000",
            "updated": "2026-04-09 18:31:00.000000",
            "status": "ACTIVE",
            "type": "MANUAL",
            "amount": {"value": "-36.00", "currency": "EUR"},
            "amount_local": {"value": "-30.00", "currency": "GBP"},
            "exchange_rate": "1.2",
            "category": "OTHER",
            "category_custom": "Brasserie 🍔",
        }
    )
    allocations = transaction["allocations"]
    allocations[0].update(
        {
            "amount": {"value": "-7.00", "currency": "EUR"},
            "amount_local": {"value": "-5.83", "currency": "GBP"},
            "type": "AMOUNT",
            "share_ratio": None,
        }
    )
    allocations[1].update(
        {
            "amount": {"value": "-29.00", "currency": "EUR"},
            "amount_local": {"value": "-24.17", "currency": "GBP"},
            "type": "RATIO",
            "share_ratio": 4,
        }
    )
    return sample_api_response


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.toml"
