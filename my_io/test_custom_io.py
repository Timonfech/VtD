import os

import aiofiles
import pytest

from my_io.custom_io import CustomAsyncBatchifier, save_file


@pytest.mark.asyncio
async def test_save_file(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("test_save_file")
    file_path = os.path.join(tmp_path, "test_file.txt")
    data = b"SOME  DATA"

    await save_file(file_path, data)

    async with aiofiles.open(file_path, 'rb') as file:
        read_data = await file.read()

    assert read_data == data


@pytest.mark.asyncio
async def test_existing_batch(tmp_path):
    # Create existing batch directory

    os.mkdir(os.path.join(tmp_path, "00001"))
    count = 0  # writes 999 files
    for i in range(998):
        file_path = os.path.join(tmp_path, "00001", f"file_{i}.txt")
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(f"{i}".encode())
            count = i

    wrighter = CustomAsyncBatchifier(tmp_path)

    data_generator = (
        (f"file_{ii}.txt", f"{ii}".encode()) for ii in range(count, count + 1003)
    )

    await wrighter.save_files_in_batches(data_generator)

    batch_dirs = sorted(os.listdir(tmp_path))
    assert len(batch_dirs) == 2
    count = 0
    for i, batch_dir in enumerate(batch_dirs):
        batch_path = os.path.join(tmp_path, batch_dir)
        assert len(os.listdir(batch_path)) == 1000
        # for file in sorted(os.listdir(batch_path)):
        #     p = os.path.join(batch_path, file)
        #     async with aiofiles.open(p, 'rb') as f:
        #         read_data = await f.read()
        #         assert int(read_data) == count
        #         count += 1


@pytest.mark.asyncio
async def test_existing_batch_chunked(tmp_path):
    # Create existing batch directory

    os.mkdir(os.path.join(tmp_path, "00003"))
    count = 0  # writes 999 files
    for i in range(998):
        file_path = os.path.join(tmp_path, "00003", f"file_{i}.txt")
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(f"{i}".encode())
            count = i

    wrighter = CustomAsyncBatchifier(tmp_path)

    data_generator = (
        (f"file_{ii}.txt", f"{ii}".encode()) for ii in range(count, count + 1003)
    )

    for file_name, content in data_generator:
        await wrighter.save_files_in_chunks(file_name, content)

    batch_dirs = sorted(os.listdir(tmp_path))
    assert len(batch_dirs) == 2
    count = 0
    for i, batch_dir in enumerate(batch_dirs):
        batch_path = os.path.join(tmp_path, batch_dir)
        assert len(os.listdir(batch_path)) == 1000


@pytest.mark.asyncio
async def test_from_0_save_files_in_chunks(tmp_path):
    # Create existing batch directory
    count = 0

    wrighter = CustomAsyncBatchifier(tmp_path)

    data_generator = (
        (f"file_{ii}.txt", f"{ii}".encode()) for ii in range(count, count + 1001)
    )

    for file_name, content in data_generator:
        await wrighter.save_files_in_chunks(file_name, content)

    batch_dirs = sorted(os.listdir(tmp_path))
    assert len(batch_dirs) == 2
    count = 0
    for i, batch_dir in enumerate(batch_dirs):
        if i == 0:
            batch_path = os.path.join(tmp_path, batch_dir)
            assert len(os.listdir(batch_path)) == 1000
        if i == 1:
            batch_path = os.path.join(tmp_path, batch_dir)
            assert len(os.listdir(batch_path)) == 1


@pytest.mark.asyncio
async def test_from_0_save_files_in_batches(tmp_path):
    # Create existing batch directory
    count = 0

    wrighter = CustomAsyncBatchifier(tmp_path)

    data_generator = (
        (f"file_{ii}.txt", f"{ii}".encode()) for ii in range(count, count + 1001)
    )

    await wrighter.save_files_in_batches(data_generator)

    batch_dirs = sorted(os.listdir(tmp_path))
    assert len(batch_dirs) == 2
    count = 0
    for i, batch_dir in enumerate(batch_dirs):
        if i == 0:
            batch_path = os.path.join(tmp_path, batch_dir)
            assert len(os.listdir(batch_path)) == 1000
        if i == 1:
            batch_path = os.path.join(tmp_path, batch_dir)
            assert len(os.listdir(batch_path)) == 1


# @pytest.mark.asyncio
# async def test_all(tmp_path_factory):
#     tmp_path = tmp_path_factory.mktemp("test_all")
#     await test_save_file(tmp_path_factory)
#     await test_existing_batch(tmp_path)
#     await test_existing_batch_chanked(tmp_path)


if __name__ == "__main__":
    pytest.main()
