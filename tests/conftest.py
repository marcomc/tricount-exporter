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
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.toml"
