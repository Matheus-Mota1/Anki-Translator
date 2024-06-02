import aiohttp
import asyncio

class ProxyDealer():
    
    def __init__(self):
        self.untested_proxies = []
        self.working = [] 
        self.not_working = []  
        self.VALID_STATUSES = [200, 301, 302, 307, 404]
        self.current_proxy = []
        
        # Desired Structure proxies = { "https": "34.195.196.27:8080", "http": "34.195.196.27:8080"}
        # It's https or a http option of the same proxy, Since the majority of the free proxies use http
        # We are going to provide only http

        with open("proxy_list.txt", "r") as f:
            self.untested_proxies = [dict(http = proxy) for proxy in f.read().strip().split("\n")]
        
        # Run the proxy testing in an asyncio event loop
        asyncio.run(self.__run())

    def __set_working(self, proxy):
        self.untested_proxies.remove(proxy)
        self.working.append(proxy)

    def __set_not_working(self, proxy):
        self.untested_proxies.remove(proxy)
        self.not_working.append(proxy)

    async def __proxy_test(self, url, proxy, session):
        try:
            async with session.get(url, proxy=f"http://{proxy['http']}", timeout=5) as response:
                if response.status in self.VALID_STATUSES:
                    # print(f"{proxy} status_code: {response.status}")
                    self.__set_working(proxy)
                else:
                    # print(f"{proxy} status_code: {response.status}")
                    self.__set_not_working(proxy)
        except Exception as e:
            self.__set_not_working(proxy)
            # print(f"{proxy} Exception: ", type(e))

    def get_proxies(self):
        # Remove the proxy and add it at the end rotating the proxies
        # proxy = self.working.pop(0)
        # self.working.append(proxy)
        # return proxy
        return self.working
       
    async def __run(self):
        # Create an aiohttp session and test each proxy
        async with aiohttp.ClientSession() as session:
            tasks = [self.__proxy_test("http://ident.me/", proxy, session) for proxy in self.untested_proxies]
            await asyncio.gather(*tasks)
        
        if len(self.working) > 0:
            total = len(self.working) + len(self.not_working)
            working_percentage = (len(self.working) / total) * 100
            print(f"Total {total} which only {working_percentage:.2f}% are available")
            print(f"working total: {len(self.working)}")
            print(f"not_working total: {len(self.not_working)}")
        else:
            raise Exception("None of the proxies in the list work")


# test = ProxyDealer()
# print(test.get_proxies())

