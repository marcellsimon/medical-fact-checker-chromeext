from openai import OpenAI
from multiprocessing import Pool
import json
import re
import os
from langchain_community.tools.pubmed.tool import PubmedQueryRun
from http.server import BaseHTTPRequestHandler, HTTPServer


def parse_json_keywords(llm_response):
    """
    Extracts and parses JSON data representing keywords from an LLM response.

    Args:
        llm_response (str): The raw response text from the LLM.

    Returns:
        list: A list of keywords extracted from the JSON, or None if no JSON was found.
    """

    # Regular expression to match the JSON array
    pattern = r'\[[^\]]*\]'
    json_match = re.search(pattern, llm_response)

    if json_match:
        json_string = json_match.group(0)
        try:
            keywords = json.loads(json_string)
            return keywords
        except json.JSONDecodeError:
            print("Error: Invalid JSON format in the response.")
            return None

    else:
        print("Error: No JSON array found in the response.")
        return None


def parse_publication_data(text):
    """Parses structured publication data into a list of dictionaries.

    Args:
        text (str): The text containing publication data.

    Returns:
        list: A list of dictionaries, each representing a publication.
    """

    publications = []
    # Split at double newlines before "Published:"
    entries = re.split(r"\n\n(?=Published:)", text)

    for entry in entries:
        publication = {}
        for line in entry.strip().splitlines():
            key, value = line.split(": ", 1)
            publication[key] = value
        publications.append(publication)

    return publications


client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ['NVIDIA_KEY']
)


def run_prompt(prompt):
    completion = client.chat.completions.create(
        model="meta/llama3-8b-instruct",
        messages=[{"role": "user",
                  "content": prompt}],
        temperature=0.2,
        top_p=1,
        max_tokens=2048,
        stream=False
    )

    response = completion.choices[0].message.content
    # print(completion.choices[0].message.content)
    # for chunk in completion:
    #     if chunk.choices[0].delta.content is not None:
    #         response += chunk.choices[0].delta.content

    return response


def get_keywords(content):
    response = run_prompt(
        f"I found a webpage with some content that I'd like to fact-check with an AI. Please give me the top 5 search phrases in a string array JSON format to check on Pubmed to find relevant publications. Return ONLY the JSON string array. It should not contain objects, just a list of strings.\n\n {content}")
    return parse_json_keywords(response)


def get_results(content, pubmed_results):
    pubmeds = "\n\n".join(pubmed_results)
    response = run_prompt(
        f"""I found a webpage with the given content that I'd like to fact-check. Please use the following format:

Content:
Multiple lines of content from the webpage that we're checking

Findings:
Relevant publications and their summaries which are in the area of the content

Evaluation:
Your evaluation if the contents of the website is valid based on the publications provided. Cite the publications when answering with title and year.

And here's the task.

Content:
{content}

Findings:
{pubmeds}

Evaluation:
"""
    )

    return response


def simplify_response(content):
    response = run_prompt(
        f"""An LLM evaluated a given content based on publications it gathered. Please make it more user friendly and concise. Write a short summary of the final results, and list all mentioned publications at the end.
Return only the reformatted text, no explanation or any other extra text. Don't write "Here is the reformatted text" or similar, ANSWER WITH THE TEXT ONLY!

The original content:
{content}

Your Summary:
""")
    return response


def get_pubmed_publication(keyword):
    tool = PubmedQueryRun()
    pubmed_results = tool.invoke(keyword)
    # return parse_publication_data(pubmed_results)
    count = pubmed_results.count("Summary::")
    print(f"Found {count} publication(s)")
    return pubmed_results


class ContentServer(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            # Parse the JSON data from the POST request
            data = json.loads(post_data.decode())
            received_content = data.get("content", None)
        except json.JSONDecodeError:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing input"}).encode())

        print("\n\n----- CONTENT:")
        print(received_content)

        keywords = get_keywords(received_content)

        print("\n\n----- KEYWORDS:")
        print(keywords)

        results = []
        for keyword in keywords:
            print("Searching publications for "+keyword)
            results.append(get_pubmed_publication(keyword))

        final_info = get_results(received_content, results)

        print("\n\n----- LLM FINDINDS:")
        print(final_info)

        simplified_response = simplify_response(final_info)

        response_data = {"message": simplified_response}

        print("\n\n----- SIMPLIFIED RESPONSE:")
        print(simplified_response)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode())


# Configure and start the server
HOST_NAME = "localhost"
PORT_NUMBER = 8000

if __name__ == '__main__':
    httpd = HTTPServer((HOST_NAME, PORT_NUMBER), ContentServer)
    print(f"Server started at http://{HOST_NAME}:{PORT_NUMBER}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()
    print("Server stopped.")


# if __name__ == '__main__':

#     # content = "Our dental office is fluoride-free. We do not provide any fluoride treatments, nor do we sell any fluoridated products because we firmly believe fluoride isn’t necessary and its use is counter-intuitive for good dental health.\n\nInstead, we only use natural solutions and products designed to work harmoniously with your oral and general health.\n\nFLUORIDE ISN’T A MIRACLE CURE FOR CAVITIES\n\nMany people were brought up to regard fluoride as being some a miracle cure for tooth decay and have been indoctrinated into using fluoridated dental products. In lots of areas, fluoride is routinely added to drinking water supplies, and its use has been attributed to a reduction in tooth decay.\n\nBut it turns out that these claims don’t add up, not least because tooth decay rates have declined in areas where fluoride isn’t used. In fact, figures from the WHO show that rates of tooth decay in the United States (where two-thirds of public water supplies are fluoridated) are higher than in countries that don’t fluoridate their water including Sweden, the Netherlands, Belgium and Denmark. Many European countries have rejected the practice of routinely fluoridating water because there is a lack of evidence that it reduces cavities and because of concerns about fluoride toxicity.\n\nCONCERNS ABOUT FLUORIDE TOXICITY\n\nParents of very young children are often advised to use non-fluoridated toothpaste up until age 2 or when the child develops the ability to spit out the excess paste. The reason for these recommendations is because when too much fluoride is ingested, it is toxic. Excess fluoride ingestion is linked to dental fluorosis, a condition that causes tooth enamel to become discoloured and which when present can indicate that the rest of your body has been overexposed to fluoride as well. In children, excess exposure to fluoride can be linked to low thyroid function, learning and behavioral difficulties and bone fragility.\n\nWE PREFER TO LOOK FOR THE CAUSE OF TOOTH DECAY\n\nCavities aren’t caused by a lack of fluoride but instead can develop due to a combination of different factors. Tooth decay can occur in teeth due to a bacterial buildup, causing infection and which can be influenced by diet and lifestyle choices, your attention to dental hygiene, and it may even be due to hereditary factors.\n\nTooth decay isn’t improved by applications of fluoride, but rather by maintaining proper dental hygiene combined with a good diet. One primary cause of cavities is excess sugar consumption and eating too many processed foods in general. Certain medications can promote tooth decay by inhibiting saliva, causing a condition called dry mouth. Being deficient in specific minerals such as magnesium can weaken teeth and bones.\n\nHere at Bel Canto Dental, our approach is to try to identify the reason for poor dental health, so we can devise a suitable treatment plan to help reduce your risk, without using fluoride or any toxic substances.\n\nBel Canto Dental can also recommend suitable fluoride-free products for use at home. By using high-quality natural products, we can take a more holistic approach to your dental care, helping to protect your oral health and especially your oral microbiome, the delicately balanced ecosystem in your mouth, which in turn helps to protect your digestive system.\n\nThe products we recommend are formulated using environmentally-friendly ingredients that help to protect and strengthen your tooth enamel naturally. They are free from artificial colours and antibacterial ingredients. Often, they are made from natural plant-based ingredients designed to reduce harmful bacteria and to freshen breath naturally."
#     # content = "The interest in Vitamin D (Vit D) is increased after the finding of Vit D receptors in many different cells. This led to the hypothesis that Vit D may have more impact on human health than its role in bone health. Epidemiological studies found associations between low plasma levels of Vit D and the prevalence of many diseases. However, Large RCTs did not find convincing evidence for a positive effect of Vit D supplementation on cancer, cardiovascular disease, auto-immune disease and inflammatory diseases. In this review, the results are described of a literature search regarding the relationship between Vit D status and different diseases. Pubmed was used to find systematic reviews of observational studies describing the association between Vit D status, diseases (cancer, coronary heart diseases, auto-immune diseases, sepsis) and mortality. Subsequently, a search was performed for RCTs and the results of large RCTs are described. Studies with a positive intervention effect on primary or secondary outcome variables are summarized. No exclusion criteria were used. The metabolism of Vit D is reviewed, its endogenous production and the intake from food, its activation and transport in the body. The article addresses the effects of diseases on the metabolism of Vit D with special focus on the role of Vit D Binding Protein and its effects on assessing Vit D status. Studies addressing the association between vitamin D status and cancer, cardiovascular diseases, auto-immune diseases, inflammation and severe illness are reviewed. A search for RCTs with positive effects of Vit D supplementation on different diseases yielded only a few studies. The vast majority of RCTs showed no significant positive effects. The presumed high prevalence of Vit D deficiency is questioned based on these results and on altered concentrations of Vit D binding protein, leading to low Vit D levels in plasma but not to low active Vit D levels during disease related inflammation In these conditions, plasma levels of Vit D are therefore not a valid reflection of Vit D status. Reversed causality is described as a possible factor interfering with the correct assessment of the Vit D status. It is concluded that further widespread fortification of foods and stimulation of supplement use should be reconsidered."
#     content = "When using leeches on humans as a therapy, we found out that the leeches who suck on people's skin who were vaccinated against sars-covid-2 die the next day. Leeches sucking other people's blood don't."
#     keywords = get_keywords(content)

#     print(keywords)

#     # with Pool(processes=5) as pool:  # Adjust the number of processes if needed
#     #     results = pool.map(get_pubmed_publication, keywords)
#     results = []
#     for keyword in keywords:
#         print(keyword)
#         results.append(get_pubmed_publication(keyword))

#     print(results[0])

#     final_info = get_results(content, results)

#     print(final_info)
