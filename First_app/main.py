import uvicorn
from fastapi import FastAPI, Depends
from fastapi.exceptions import HTTPException 
from pydantic import BaseModel

from typing import Annotated

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class User(BaseModel):
    username: str
    email: str
    fullname: str
    disabled: bool

   
class UserInDb(User):
    hashed_password: str

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "email": "johndoe@gmail.com",
        "fullname": "John Doe",
        "hashed_password": "fakehashedsecret",
        "disabled": True
    },
    "alice": {
        "username": "alice",
        "email": "alice20@gmail.com",
        "fullname": "Alice Wonderson",
        "hashed_password": "fakehashedsecret2",
        "disabled": False  
    }
}   

def fake_password_hasher(password):
    return f"fakehashed{password}"

def get_user(db, username):
    if username in db:
        user_dict = fake_users_db[username]
        user = UserInDb(**user_dict)
        return user     
    
def fake_decode_token(token):
    user = get_user(fake_users_db, token)
    if not user:
        raise HTTPException(status_code=400, detail="incorrect username or password")
    return user
    
def get_current_user(token: str = Depends(oauth2_scheme)):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid Authentication Credentials", headers={"WWW-Authenticate": "Bearer"})
    return user
    
    
def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive User")
    return current_user
    
@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = fake_decode_token(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail= "incorrect username or password")
    hashed_password = fake_password_hasher(form_data.password)
    
    import secrets
    #if hashed_password != user.hashed_password:
    if not secrets.compare_digest(hashed_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="incorrect username or password")
    return {"access_token": user.username, "token_type": "Bearer"}
    
@app.get("/users/me")
async def read_users_me(user: User = Depends(get_current_active_user)):
    return user
    
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

