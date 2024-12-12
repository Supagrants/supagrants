"""
4.2
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReplaceOne

from config import MONGO_SERVER, MONGO_PORT, MONGO_DB, MONGO_CONNECTION, logger


class Mongo():
    def __init__(self, db=MONGO_DB, server=MONGO_SERVER, port=MONGO_PORT, connection=MONGO_CONNECTION):
        self.client = None
        self.db = db
        self.server = server
        self.port = port
        self.connection = connection
        self.connect()

    def connect(self):
        try:
            if self.client:
                self.client.close()

            if self.connection:
                self.client = AsyncIOMotorClient(self.connection, maxPoolSize=10)
            else:
                self.client = AsyncIOMotorClient(self.server, self.port)
            self.mongo = self.client[self.db]
        except Exception as e:
            logger.error(f'MONGO: connect failed {e}')

    async def search(self, query, collection, skip=0, limit=100, projection=None, sort=None):
        try:
            limit = int(limit)
            mycol = self.mongo[collection]
            if sort:
                res = mycol.find(query, projection).sort(sort).skip(skip)
            else:
                res = mycol.find(query, projection).skip(skip).limit(limit)
            res = await res.to_list(length=limit)
            return res
        except Exception as e:
            logger.error(f'MONGO: {e} search for {query}')

    async def search_one(self, query, collection, projection=None, sort=None):
        try:
            mycol = self.mongo[collection]
            if sort:
                res = mycol.find_one(query, projection).sort(sort)
            else:
                res = mycol.find_one(query, projection)
            return await res
        except Exception as e:
            logger.error(f'MONGO: {e} search for {query}')

    async def distinct(self, key, query, collection):
        try:
            mycol = self.mongo[collection]
            res = await mycol.distinct(key, filter=query)
            return res
        except Exception as e:
            logger.error(f'MONGO: {e} distinct search for {key}')

    async def aggregate(self, steps, collection, limit=1e6):
        try:
            mycol = self.mongo[collection]
            res = mycol.aggregate(steps)
            return await res.to_list(length=int(limit))
        except Exception as e:
            logger.error(f'MONGO: {e} failed on aggregate for {steps}')

    async def get(self, id, collection, projection=None):
        try:
            mycol = self.mongo[collection]
            res = await mycol.find_one({'_id': id}, projection)
            return res
        except:
            logger.error(f'MONGO: failed on get for {id}')

    async def update(self, item, collection):
        try:
            c = self.mongo[collection]
            await c.replace_one({'_id': item['_id']}, item, upsert=True)
        except Exception as e:
            logger.error(f'MONGO: failed on update {e}')

    async def updateFields(self, id, fields, collection):
        try:
            c = self.mongo[collection]
            query = {"$set": fields}
            await c.update_one({'_id': id}, query, upsert=True)
        except:
            logger.error(f'MONGO: failed on updateFields for {id}')

    async def updateFieldsQuery(self, query, fields, collection, update=None):
        try:
            c = self.mongo[collection]
            update = {"$set": fields} if not update else update
            await c.update_one(query, update, upsert=True)
        except:
            logger.error(f'MONGO: failed on updateFields for {query}')

    async def updateMany(self, query, field, value, collection):
        try:
            c = self.mongo[collection]
            await c.update_many(query, {'$set': {field: value}})
        except:
            logger.error(f'MONGO: failed on update many for {query}')

    async def updateBulk(self, items, collection):
        try:
            # Create a list of UpdateOne operations based on the documents_to_update list
            bulk_operations = [
                ReplaceOne(
                    {"_id": doc["_id"]},  # Match each document by its _id
                    doc,  # The new document to replace the existing one
                    upsert=True  # Set to True to insert if the document doesn't exist
                )
                for doc in items
            ]
            c = self.mongo[collection]
            await c.bulk_write(bulk_operations)
        except Exception as e:
            logger.error(f'MONGO: failed on bulk update')

    async def delete(self, query, collection):
        try:
            c = self.mongo[collection]
            await c.delete_many(query)
        except:
            logger.error(f'MONGO: failed on delete for {query}')

    async def insert(self, item, collection):
        c = self.mongo[collection]
        if item and isinstance(item, list):
            result = await c.insert_many(item, ordered=False)
        elif item:
            await c.insert_one(item)

    async def insertBatches(self, item, collection, batchSize=100):
        if isinstance(item, list):
            size = len(item)
            limit = batchSize
            max = int(size / limit)
            max = max + 1 if size % limit != 0 else max  # add one more round if extra items
            for i in range(0, max):
                start = i * limit
                end = min(start + limit, size)
                batch = item[start:end]
                try:
                    await self.updateBulk(batch, collection)
                    logger.info(f'MONGO: Batch insert {i}')
                except Exception as e:
                    # failed, thus try item by item
                    logger.warning(f'MONGO: Batch error saving item single in batch {i}')
                    for i in batch:
                        await self.update(i, collection)
        else:
            return await self.insert(item, collection)

    async def getCollections(self):
        out = await self.mongo.list_collection_names()
        return out
