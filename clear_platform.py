import sys
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

platform = sys.argv[1].upper()
uri = os.getenv(f"{platform}_URI")
user = os.getenv(f"{platform}_USER")
password = os.getenv(f"{platform}_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(user, password))
with driver.session() as session:
    session.run("MATCH (n) DETACH DELETE n").consume()
driver.close()
print(f"{platform} cleared")