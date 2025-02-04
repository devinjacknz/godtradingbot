from typing import Any, Dict

API_CREDENTIALS: Dict[str, Dict[str, Any]] = {
    "trading_client": {
        "client_id": "a3e2d3f54b3416c87c25630e9431adce",
        "secret_key": "S133Er8Btn7Fji8dSBuygD0AiB8Pb_A5EF9B7tZYSJH3ND2W_idiumwDOoFePuw9YaS-k_suOPr5eIUP_3gDwg",
    }
}


def get_credentials(service: str) -> Dict[str, Any]:
    return API_CREDENTIALS.get(service, {})
