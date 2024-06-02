import os
import sqlite3
from zipfile import ZipFile
from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound, TooManyRequests
from requests.exceptions import ProxyError, ConnectTimeout
from tqdm import tqdm
from proxy_dealer import ProxyDealer
import logging
import asyncio
import aiohttp
import json

class DeckManipulator:

    def __init__(self):
        self.origin_path = "decks"
        self.destiny_path = "translated_decks"
        self.temp_file = os.path.join(self.destiny_path, "temp_file")
        proxy_dealer = ProxyDealer()
        self.proxies = proxy_dealer.get_proxies()
        logging.basicConfig(filename='deck_manipulator.log', level=logging.INFO)
        self.field_names = ["tradução", "significado"]

    def extract_apkg(self, apkg_file, extract_to):
        with ZipFile(apkg_file, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

    def create_apkg(self, folder, output_file):
        with ZipFile(output_file, 'w') as zipf:
            for root, dirs, files in os.walk(folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder)
                    zipf.write(file_path, arcname)

    def list_decks(self):
        decks = os.listdir(self.origin_path)
        full_path_decks = [os.path.join(self.origin_path, deck) for deck in decks]
        return full_path_decks

    def remove_temporary_files(self, path):
        for root, dirs, files in os.walk(path, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        print("Temporary files removed")

    def connect_to_database(self, sql_folder):
        db_path = os.path.join(sql_folder, 'collection.anki2')
        conn = sqlite3.connect(db_path)
        return conn, conn.cursor()

    async def translate_text(self, text):
        async with aiohttp.ClientSession() as session:
            for proxy in self.proxies:
                try:
                    translator = GoogleTranslator(source='en', target='pt', proxies=proxy)
                    translated = translator.translate(text)
                    return translated
                except (TranslationNotFound, TooManyRequests, ProxyError, ConnectTimeout) as e:
                    logging.error(f"Error with proxy: {proxy}: {e}")
                except Exception as e:
                    logging.error(f"Unexpected error with proxy: {proxy}: {e}")
        print("All the proxies failed, please wait 60 seconds, and the programm will continue...")
        await asyncio.sleep(60)
        return await self.translate_text(text)
    
    def get_field_indices(self, cursor):
        cursor.execute("SELECT models FROM col")
        models_json = json.loads(cursor.fetchone()[0])
        field_indices = {}

        for model_id, model_data in models_json.items():
            indices = {}
            for field in model_data['flds']:
                # If the field name is equal to the field name we provided it saves the index of that field
                if field['name'] in self.field_names:
                    indices[field['name']] = model_data['flds'].index(field)
            if indices:
                field_indices[model_id] = indices
            
        # It will return the following structure:
        # {'model_id': {'field_name': field_index, 'field_name': field_index}, 'model_id_n': ...}
        # Basically the 'model_id' and the fields of the model, each field a pair value of name: index

        if field_indices:
            return field_indices
        else:
            raise Exception("Please provide valid field names")

    async def manipulate_fields(self, conn, cursor, file_name=""):
        field_indices = self.get_field_indices(cursor)
        
        # **id**: ID da nota.
        # **mid**: ID do modelo de nota (relacionado à tabela `models` no campo `models` da tabela `col`).
        # **flds**: Campos da nota, separados por `\x1f`.

        cursor.execute("SELECT id, mid, flds FROM notes")
        notes = cursor.fetchall()

        # Will get through all the cards in the deck, check the comment above to understand
        for note_id, mid, flds in tqdm(notes, desc=f"Translating fields {file_name}"):
            fields = flds.split('\x1f')
            # print(note_id, mid, fields)
            if str(mid) in field_indices:
                # Identify the card structure them loop through field_name:index
                for field_name, index in field_indices[str(mid)].items():
                    translated_field = await self.translate_text(fields[index])
                    fields[index] = translated_field
            new_flds = '\x1f'.join(fields)
            cursor.execute("UPDATE notes SET flds = ? WHERE id = ?", (new_flds, note_id))
        conn.commit()

    async def run(self):
        decks = self.list_decks()
        for deck in decks:
            deck_file_name = os.path.basename(deck)
            output_file = os.path.join(self.destiny_path, deck_file_name)

            self.extract_apkg(deck, self.temp_file)
            conn, cursor = self.connect_to_database(self.temp_file)
            await self.manipulate_fields(conn, cursor, deck_file_name)
            self.create_apkg(self.temp_file, output_file)
            self.remove_temporary_files(self.temp_file)
            conn.close()

if __name__ == "__main__":
    deck_manipulator = DeckManipulator()
    asyncio.run(deck_manipulator.run())

