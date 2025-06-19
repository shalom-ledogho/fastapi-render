from fastapi import FastAPI, Depends, status
from fastapi.exceptions import HTTPException 
from sqlmodel import (
    SQLModel, Field, create_engine, select, Session, 
    text, Relationship
)
from typing import Optional, Annotated
import uvicorn
from contextlib import asynccontextmanager

# team MODELS
class TeamBase(SQLModel):
    name: str = Field(index = True)
    headquarters: str

class Team(TeamBase, table = True):
    id: Optional[int] = Field(default = None, primary_key = True) 

    heroes: list['Hero'] = Relationship(back_populates = "team")

class TeamCreate(TeamBase):
    pass
    
class TeamUpdate(SQLModel):
    name: Optional[str] = None
    headquarters: Optional[str] = None

class TeamPublic(TeamBase):
    id: int
       
class TeamPublicWithHeroes(TeamBase):
    id: int
    
    heroes: list['HeroPublic'] = []
    
# hero MODELS
class HeroBase(SQLModel):
    name: str = Field(index = True)
    age: Optional[int] = Field(default = None, index = True)
    
    team_id: Optional[int] = Field(default = None, foreign_key = "team.id", ondelete = 'SET NULL')
        
class Hero(HeroBase, table = True):
    id: Optional[int] = Field(default = None, primary_key = True)
    secret_name: str
    hashed_password: str
    
    team: Team = Relationship(back_populates = 'heroes')
    
class HeroCreate(HeroBase):
    secret_name: str
    password: str
    
class HeroPublic(HeroBase):
    id: int
    
    
class HeroPublicWithTeam(HeroBase):
    id: int
    
    team: Optional[TeamPublic] = None
    
class HeroUpdate(SQLModel):
    name: Optional[str] = None
    secret_name: Optional[str] = None
    age: Optional[int] = None
    team_id: Optional[int] = None
    password: Optional[str] = None
    
def hash_password(password):
    return f'#$%{password}'
    
def session_dep():
    with Session(engine) as session:
        yield session
        
SessionDep = Annotated[Session, Depends(session_dep)]
    
sqlite_file_name = 'database.db'
sqlite_url = f'sqlite:///{sqlite_file_name}'
connect_args = {'check_same_thread': False}
engine = create_engine(sqlite_url, echo = True, connect_args = connect_args)

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(lifespan = lifespan)

'''
@app.on_event("startup")
async def create_db_and_tables():
    # create database and tables
    SQLModel.metadata.create_all(engine)
'''
    
# team routes
@app.post('/teams', response_model = TeamPublicWithHeroes, tags = ['team'])
async def create_teams(session: SessionDep, team: TeamCreate):
    # validate database team model using team creation model
    db_team = Team.model_validate(team)
    
    # save database team to the database
    session.add(db_team)
    session.commit()
    session.refresh(db_team)
    
    # return the database team
    return db_team
    
@app.get('/teams', response_model = list[TeamPublicWithHeroes], tags = ["team"])
async def fetch_all_teams(session: SessionDep):
    
    # get all team from the database
    statement = select(Team)
    db_teams = session.exec(statement).all()
    if not db_teams:
        raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = 'no records found')
    return db_teams

@app.get('/teams/{team_id}', response_model = TeamPublicWithHeroes, tags = ["team"])
async def fetch_one_team(session: SessionDep, team_id: int):
    # first check if team_id exist in any team
    statement = select(Team)
    db_teams = session.exec(statement).all()
    id_list = []
    for team in db_teams:
        id_list.append(team.id)
        
    if team_id not in id_list:
        raise HTTPException(status_code = 404, detail = f'team with team id {team_id} not found')
    
    # if it exist, get the team with that id and return that team
    db_team = session.get(Team, team_id)
    return db_team
    
@app.patch('/teams/{team_id}', response_model = TeamPublicWithHeroes, tags = ["team"])
async def update_team(session: SessionDep, team_id: int, team: TeamUpdate):
    # first check if that team_id exist in any team and
    # return a nice clean error it it doesn't
    statement = select(Team)
    db_team = session.exec(statement).all()
    id_list = []
    for team in db_team:
        id_list.append(team.id)
        
    if team_id not in id_list:
        raise HTTPException(status_code = 404, detail = f'team with team id {team_id} not found')
    
    # if it exist get the team with that id 
    db_team = session.get(Team, team_id)
    
    # get the team update data
    team_update_data = team.model_dump(exclude_unset = True)
    
    # update the team
    db_team.sqlmodel_update(team_update_data)
    
    # save the team to the database
    session.add(db_team)
    session.commit()
    session.refresh(db_team)
    
    # return the updated team after saving it
    return db_team
    
@app.delete('/teams/{team_id}', tags = ["team"])
async def delete_one_team(session: SessionDep, team_id: int):
    # check if team id belongs to a hero and return an
    # error if it doesn't
    statement = select(Team)
    db_team = session.exec(statement).all()
    
    id_list = []
    for team in db_team:
        id_list.append(team.id)
        
    if team_id not in id_list:
        raise HTTPException(status_code = 404, detail = f'hero with id {hero_id} not found')
    
    # if it exist, get the team with that id
    db_team = session.get(Team, team_id)
     
    #delete that team and save changes
    session.delete(db_team)
    session.commit()
    
    return  f'team {db_team.name} deleted successfully'

@app.delete('/teams', tags = ["team"])
async def delete_all_team(session: SessionDep):
    # get all team in the database as a list
    statement = select(Team)
    db_team = session.exec(statement).all()
    
    # clear all those team from the list of team
    for team in db_team:
        session.delete(team)
    session.commit()
    
    return 'you have deleted all team'

# hero routes
@app.post('/heroes', response_model = HeroPublicWithTeam, tags = ["hero"])
async def create_hero(*, session: SessionDep, hero: HeroCreate):
    # get the hero create data 
    hero_create_data = hero.model_dump(exclude_unset = True)
    
    # create a hashed password for database hero using the password in the 
    # hero create data
    hashed_password = hash_password(hero.password)
    extra = {}
    extra['hashed_password'] = hashed_password
    
    # get list of all existing passwords
    pwd_list = []
    
    statement = select(Hero)
    db_hero = session.exec(statement).all()
    
    for ahero in db_hero:
        pwd_list.append(ahero.hashed_password)
        
    # create the database hero
    db_hero = Hero.model_validate(hero, update = extra)
    
    # if database hero hashed_password already exist, return an error 
    if db_hero.hashed_password in pwd_list:
        #raise SQLModel.exceptions.IntegrityError
        raise HTTPException(status_code = 409, detail = f'password {hero.password} already taken')    
    
    
    # if it doesn't, save the database hero 
    session.add(db_hero)
    session.commit()
    session.refresh(db_hero)
    
    # return the response showing the created hero
    return db_hero
    
'''
def create_fake_hero():
    pwd_list = []
    
    with Session(engine) as session:
        statement = select(Hero)
        db_hero = session.exec(statement).all()
    
        for ahero in db_hero:
            pwd_list.append(ahero.hashed_password)
        
        fake_hero = Hero(id = 3, name = "Shalom", age = 26, secret_name = "Ledogho", team_id = 1, hashed_password = "#$%secreting")
    
        if fake_hero.hashed_password in pwd_list:
            #raise sqlalchemy.exc.IntegrityError
            raise HTTPException(status_code = 409, detail = f'password  already taken')    
    
    
        session.add(fake_hero)
        session.commit()
        session.refresh(fake_hero)
    
create_fake_hero()
'''   
             
@app.get('/heroes', response_model = list[HeroPublicWithTeam], tags = ["hero"])
async def get_all_hero(*, session: SessionDep):
    statement = select(Hero)
    db_heroes = session.exec(statement).all()
    
    if not db_heroes:
        raise HTTPException(status_code = 404, detail = ' no records found')
        
    return db_heroes
    
@app.get('/heroes/{hero_id}', response_model = HeroPublicWithTeam, tags = ["hero"])
async def get_one_hero(*, session:SessionDep, hero_id: int):
    # first check if hero_id exist in any hero
    statement = select(Hero)
    db_hero = session.exec(statement).all()
    id_list = []
    for hero in db_hero:
        id_list.append(hero.id)
        
    if hero_id not in id_list:
        raise HTTPException(status_code = 404, detail = f'hero with id {hero_id} not found')
    
    # if it exist, get the hero with that id and return that hero
    db_hero = session.get(Hero, hero_id)
    return db_hero
    
@app.patch('/heroes/{hero_id}', response_model = HeroPublicWithTeam, tags = ["hero"])
async def update_heroes(*, session: SessionDep, hero_id: int, hero: HeroUpdate):
    # get list of existing id's and passwords 
    statement = select(Hero)
    db_heroes = session.exec(statement).all()
    
    id_list = []
    for ahero in db_heroes:
        id_list.append(ahero.id)
        
    pwd_list = []
    for ahero in db_heroes:
        pwd_list.append(ahero.hashed_password)
        
    # check if id exist
    if hero_id not in id_list:
        raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = f'hero with id {hero_id} not found')
    
    # if the id exist, get the db hero to update and hero update data
    db_hero = session.get(Hero, hero_id)
            
    hero_update_data = hero.model_dump(exclude_unset = True)
    
    # check if update data comes with a password.
    extra = {}
    
    if 'password' in hero_update_data:
        if hash_password(hero.password) == db_hero.hashed_password:
            hashed_password = hash_password(hero.password)
            extra['hashed_password'] = hashed_password
            db_hero.sqlmodel_update(hero_update_data, update = extra)
        else:
            raise HTTPException(status_code = status.HTTP_409_CONFLICT, detail = 'password already taken')
    else:
        db_hero.sqlmodel_update(hero_update_data)
        
    session.add(db_hero)
    session.commit()
    session.refresh(db_hero)    
    return db_hero
    


@app.delete('/heroes', tags = ["hero"])
async def delete_all_hero(session: SessionDep):
    statement = select(Hero)
    db_hero = session.exec(statement).all()
    
    for hero in db_hero:
        session.delete(hero)
        
    session.commit()
    
    return 'heroes deleted'
    
@app.delete('/heroes/{hero_id}', tags = ["hero"])
async def delete_one_hero(*, session:SessionDep, hero_id: int):
    db_hero = session.get(Hero, hero_id)
    
    if not db_hero:
        raise HTTPException(status_code = status.HTTP_404_NOT_FOUND)
    
    session.delete(db_hero)
    session.commit()
    
    return f'hero {db_hero.name} deleted'

if __name__ == "__main__":
    uvicorn.run(app, host='127.0.0.1', port=8000)
    

