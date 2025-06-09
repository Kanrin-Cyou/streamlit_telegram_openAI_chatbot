from duckduckgo_search import DDGS
from tools.general_utils import async_web_crawler
from openai import AsyncOpenAI
import asyncio
import time

import configparser
config = configparser.ConfigParser()
config.read('config.ini')
OPENAI_API_KEY = config.get('default', 'OPENAI_API_KEY')
openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

ddgs = DDGS()
max_results = 8

# evaluate if the web snippet is relevant to the keywords
async def website_evaluate(web_snippet, keywords, question):
    """
    Evaluate if the web snippet is relevant to the keywords.
    """
    command = f"""
    You will be given a website snippet from internet.
    Please check if it's revelant to ${keywords} and will be helpful to answer the question:{question}
    If it is relevant, return True, otherwise return False.
    """
    init_chat = [
        {
            "role": "system",
            "content": command,
        },
        {
            "role": "user",
            "content": web_snippet
        }
    ]
    response = await openai.responses.create(
        model="gpt-4.1-nano",
        temperature=0.3,
        input=init_chat,
    )
    if response.output_text.lower() in ["true", "yes", "relevant"]:
        return True
    else:
        return False

async def web_search(keywords, question):
    """
    Search the internet for the given keywords and return the content.
    """

    evaluated_results = []
    final_result = []
    wikipedia = search_internet_wiki(keywords)

    search_results = []    
    search_results += wikipedia
    
    web_resources = search_internet(keywords, max_results)   
    for web_resource in web_resources:
        if web_resource['href'].find("wikipedia.org")==-1:
            search_results.append(web_resource)
    
    print("---")
    print("search_results")
    print("---")
    for search_result in search_results:
        print(f"{search_result['title']}: {search_result['href']} \n")
    
    if not search_results:
        return []
    
    async def evaluate_content(search_result):
        if 'href' in search_result.keys():  
            if_relevant = await website_evaluate(search_result['body'], keywords, question)
            if if_relevant:
                evaluated_results.append(search_result)
    
    start = time.time()
    coros_evaluation = [evaluate_content(search_result) for search_result in search_results]
    await asyncio.gather(*coros_evaluation)
    e1 = time.time()
    print("---")
    print("evaluated_results")
    print(f"Cost:{round(e1-start,2)}s")
    print("---")
    for evaluated_result in evaluated_results:
        print(f"{evaluated_result['title']}: {evaluated_result['href']} \n")
        
    async def content_formating(search_result):
        body = await async_web_crawler(search_result['href'])          
        if body:
            final_result.append({
                'title': search_result['title'],
                'href': search_result['href'],
                'body': body
            })            
    
    coros_preprocessing = [content_formating(search_result) for search_result in evaluated_results[:8]]
    await asyncio.gather(*coros_preprocessing)
    e2 = time.time()    
    print("---")
    print("final_results")
    print(f"Cost:{round(e2-e1,2)}s")
    print("---")
    for single_result in final_result:
        print(f"{single_result['title']}: {single_result['href']} \n")
        
    return final_result

def search_internet(keyword, max_results):
    try:
        results = ddgs.text(keyword, max_results)
        # Filter out irrelevant results
        filtered_results = [result for result in results if 'body' in result]
        return filtered_results
    except Exception as e:
        print(f"Error searching internet: {e}")
        return []
    
def search_internet_wiki(keywords:str):
    """
    Search Wikipedia for the given keywords and return the content.
    """
    answer = []

    results = search_internet(keywords+" wikipedia", 2)
    if(len(results)==0):
        return []
    for result in results:
        title = result['title']
        wikipedia_url = result['href']
        wikipedia_body = result['body']
        if wikipedia_url.find("wikipedia.org")!=-1:
            wikipedia_result = {
                    'title': title,
                    'href': wikipedia_url,
                    'body': wikipedia_body
                }
            answer.append(wikipedia_result)
    return answer



