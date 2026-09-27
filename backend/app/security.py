import base64,hashlib,hmac,json,time
from typing import Any
from cryptography.fernet import Fernet

def encrypt_secret(key:str,value:str)->str:
    return Fernet(key.encode()).encrypt(value.encode()).decode()

def sign_state(secret:str,payload:dict[str,Any])->str:
    body=json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
    encoded=base64.urlsafe_b64encode(body).decode().rstrip("=")
    signature=hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
    return encoded+"."+signature

def verify_state(secret:str,state:str,max_age_seconds:int=600)->dict[str,Any]:
    encoded,signature=state.rsplit(".",1)
    expected=hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected): raise ValueError("Invalid OAuth state signature")
    payload=json.loads(base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)))
    if time.time()-float(payload["iat"])>max_age_seconds: raise ValueError("OAuth state expired")
    return payload
