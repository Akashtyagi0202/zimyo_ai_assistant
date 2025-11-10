# services/policy_service.py
import logging


from datetime import date,timedelta
import requests, pdfplumber
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

logger = logging.getLogger(__name__)

def extract_policies(policyLists:list)->list:
    policies = []
    stack = policyLists
    
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            policies_file = item.get('POLICIES_FILE')
            policies_name = item.get('POLICIES_NAME')
            if policies_file and policies_name:
                policies.append({
                    'policy_name': policies_name,
                    'policy_url': policies_file
                })
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    
    return policies


def download_and_extract_pdf(item:dict)->dict:
    policy_extracted_data = {}
    try:
        response = requests.get(item['policy_url'])
        response.raise_for_status()
        pdf_content = BytesIO(response.content)
        pdf_content.seek(0)
        
        text = ""
        with pdfplumber.open(pdf_content) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
                text += "\n"
        
        policy_extracted_data[item['policy_name']] = text
        print("PDF file downloaded and text extracted:", item['policy_name'])
        
    except requests.exceptions.RequestException as e:
        print(f"Request error downloading PDF file {item['policy_name']}: {e}")
    except Exception as e:
        print(f"Error processing PDF file {item['policy_name']}: {e}")
        
    return policy_extracted_data

def process_pdfs_concurrently(policies_file_data, max_workers=3):
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_and_extract_pdf, item) for item in policies_file_data]
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.update(result)
            except Exception as e:
                print(f"An error occurred: {e}")
                continue
    return results