import asyncio
import math
import os
from typing import AsyncGenerator, Union

import aiofiles


async def save_file(file_path: str, data: bytes):
    async with aiofiles.open(file_path, 'wb') as file:
        await file.write(data)


def count_digits(n):
    if n == 0:
        return 1
    return math.floor(math.log10(abs(n))) + 1


class CustomAsyncBatchifier:
    def __init__(self, base_dir_path: str, leading_value=0, leading_count=5, batch_size=1000):
        self.current_batch_dir: str = None
        self.files_at_batch_count = 0
        self.files_saved = 0
        self.lock = asyncio.Lock()
        self.base_dir_path = base_dir_path
        self.leading_value = leading_value
        self.leading_count = leading_count
        self.BUTCH_SIZE = batch_size
        if not os.path.exists(base_dir_path):
            os.makedirs(base_dir_path)
        else:
            self.set_init_folder()

    def set_init_folder(self):

        existing_batches = [d for d in os.listdir(self.base_dir_path) if
                            os.path.isdir(os.path.join(self.base_dir_path, d))]
        if len(existing_batches) > 0:
            last_batch_dir = max(existing_batches)
            last_batch_path = os.path.join(self.base_dir_path, last_batch_dir)
            self.current_batch_dir = last_batch_path
            self.files_at_batch_count = len(
                [f for f in os.listdir(last_batch_path) if os.path.isfile(os.path.join(last_batch_path, f))]) - 1
        else:
            self.current_batch_dir = os.path.join(self.base_dir_path,
                                                  f'{1:0{self.leading_count}d}')

            os.mkdir(self.current_batch_dir)

    def batchifier(self):
        if self.files_at_batch_count < self.BUTCH_SIZE:
            self.files_at_batch_count += 1
            return
        last_batch_number = int(os.path.basename(self.current_batch_dir))
        num_of_dig = count_digits(last_batch_number)
        if num_of_dig > self.leading_count:
            self.current_batch_dir = os.path.join(self.base_dir_path,
                                                  f'{last_batch_number + 1:0{self.leading_count + 1}d}')
        else:
            self.current_batch_dir = os.path.join(self.base_dir_path,
                                                  f'{last_batch_number + 1:0{self.leading_count}d}')
        self.files_at_batch_count = 0
        os.mkdir(self.current_batch_dir)

    async def save_files_in_batches(self, data_generator):
        for file_name, data in data_generator:
            async with self.lock:
                self.batchifier()
            file_path = os.path.join(self.current_batch_dir, file_name)
            await save_file(file_path, data)
            self.files_saved += 1

    async def save_files_in_chunks(self, file_name: str, data: Union[bytes, AsyncGenerator]):
        async with self.lock:
            self.batchifier()

        file_path = os.path.join(self.current_batch_dir, file_name)
        try:
            if isinstance(data, AsyncGenerator):
                async with aiofiles.open(file_path, 'wb') as file:
                    async for chunk in data:
                        await file.write(chunk)
            if isinstance(data, bytes):
                async with aiofiles.open(file_path, 'wb') as file:
                    await file.write(data)
            async with self.lock:
                self.files_saved += 1
        except FileNotFoundError:
            self.set_init_folder()
            await self.save_files_in_chunks(file_name, data)
