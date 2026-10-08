from typing import Annotated, Generator
from fastapi import Depends
from supabase import Client, create_client
from app.config import settings

def get_db() -> Generator[Client, None, None]:
	client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
	try:
		yield client
	finally:
		pass

SupabaseClient = Annotated[Client, Depends(get_db)]
