# 1. GET https://api.modrinth.com/v2/search?facets=[["categories:fabric"]]&offset={offset}&limit=100
# 2. GET https://api.modrinth.com/v2/project/{pid}/version

import asyncio
import aiohttp
import json


async def main():
    sp_map = await build_spmap()
    print("spmap builted.")
    project_ids = sp_map.values()
    _, ratelimit = await get_projects_number_and_ratelimit()
    # build and save dependency file
    ## split tasks if ratelimit is not enough
    tasks_list = []
    part_tasks = []
    for pid in project_ids:
        if ratelimit <= 5:
            tasks_list.append(part_tasks)
            part_tasks = []
            ratelimit = 300
        part_tasks.append(fetch_dependencies(pid))
        ratelimit -= 1
    tasks_list.append(part_tasks)
    ## start fetch data and save to file
    count = 0
    for i in tasks_list[:-1]:
        for result in await asyncio.gather(*i):
            for pid in result.keys():
                with open(f"depot/{pid}.json", "w") as f:
                    json.dump(result[pid], f)
                count += 1
        print(f"current progress: {count}/{len(project_ids)}", "sleep 60s")
        await asyncio.sleep(60)
    for result in await asyncio.gather(*tasks_list[-1]):
        for pid in result.keys():
            with open(f"depot/{pid}.json", "w") as f:
                json.dump(result[pid], f)



async def fetch_dependencies(pid):
    """fetch dependencies of a project"""
    result = {}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://api.modrinth.com/v2/project/{pid}/version") as response:
                data = await response.json()
                dependencies = []
                try:
                    for version in data:
                        if "fabric" in version["loaders"]:
                            dep_format = {}
                            dep_format["game_versions"] = version["game_versions"]
                            dep_format["version_number"] = version["version_number"]
                            dep_format["dependencies"] = [d["project_id"] for d in version["dependencies"]]
                            dependencies.append(dep_format)
                    result[pid] = dependencies
                except TypeError as e:
                    print(f"triggered {e}:\n{data}")
        except aiohttp.client_exceptions.ContentTypeError as _:  # if project be deleted or hidden
            print(f"{pid} dispaired.")
    return result

async def build_spmap():
    """build slug -> pid map **and save to depot/map.json**"""
    sp_map = {}
    total_number, ratelimit = await get_projects_number_and_ratelimit()
    print(
        "total number:",
        total_number,
        "request need:",
        total_number // 100 + 1,
        "ratelimit remain:",
        ratelimit,
    )
    # split tasks if ratelimit is not enough
    tasks_list = []
    part_tasks = []
    for offset in range(0, total_number, 100):
        if ratelimit <= 5:
            tasks_list.append(part_tasks)
            part_tasks = []
            ratelimit = 300
        part_tasks.append(fetch_projects(offset))
        ratelimit -= 1
    tasks_list.append(part_tasks)
    # start fetch data
    for i in tasks_list[:-1]:
        for result in await asyncio.gather(*i):
            sp_map.update(result)
        print("current map length:", len(sp_map), "sleep 60s")
        await asyncio.sleep(60)
    for result in await asyncio.gather(*tasks_list[-1]):
        sp_map.update(result)
    # save map to file
    with open("depot/map.json", "w") as f:
        json.dump(sp_map, f)
    return sp_map

async def get_projects_number_and_ratelimit():
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f'https://api.modrinth.com/v2/search?facets=[["categories:fabric"]]&limit=1'
        ) as response:
            data = await response.json()
            return data["total_hits"], int(response.headers["x-ratelimit-remaining"])


async def fetch_projects(offset):
    """fetch 100 projects and build slug -> pid map"""
    result = {}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f'https://api.modrinth.com/v2/search?facets=[["categories:fabric"]]&offset={offset}&limit=100'
        ) as response:
            data = await response.json()
            # print("retelimit remain:", response.headers["x-ratelimit-remaining"])
            for mod in data["hits"]:
                result[mod["slug"]] = mod["project_id"]
        return result


asyncio.run(main())
