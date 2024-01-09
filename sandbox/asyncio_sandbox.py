import asyncio


async def main():
    task = asyncio.create_task(main2())
    print("A")
    await asyncio.sleep(1)
    print("B")


async def main2():
    print("1")
    await asyncio.sleep(2)
    print("2")

asyncio.run(main())
