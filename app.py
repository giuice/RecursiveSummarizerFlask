import math
import traceback
from flask import Flask, render_template, request, flash, redirect
import openai
from youtube_transcript_api import YouTubeTranscriptApi
import json
import requests
import textwrap
import spacy
from spacy.lang.en.stop_words import STOP_WORDS

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import en_core_web_sm
app = Flask(__name__)
app.secret_key = 'my_secret_key_1234'
id_ = ''

nlp = en_core_web_sm.load(exclude=["tagger", "parser", "senter", "attribute_ruler", "lemmatizer", "ner"])
nlp.add_pipe('sentencizer')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_url = request.form['video_url']
        language = request.form['language']
        transcript = get_transcript(video_url)
        summarized_transcript, error = summarize_transcript2(transcript, language)

        if error:
            flash(error)
            return redirect('/')
        return render_template('index.html', summary_array=summarized_transcript)
    return render_template('index.html')

def file_exists(file):
    try:
        with open(file, 'r') as f:
            return True
    except IOError:
        return False
    except:
        raise

def get_transcript(video_url):
    _id = video_url.split("=")[1].split("&")[0]
    transcript = YouTubeTranscriptApi.get_transcript(_id)
    return transcript

API_KEY = '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'

def pagerank(M, d=0.85, eps=1.0e-8):
    N = M.shape[0]
    v = np.random.rand(N, 1)
    v = v / np.linalg.norm(v, 1)
    last_v = np.ones((N, 1), dtype=np.float32) * np.inf
    M_hat = (d * M) + (((1 - d) / N) * np.ones((N, N)))
    while np.linalg.norm(v - last_v, 2) > eps:
        last_v = v
        v = M_hat @ v
    return v


def create_similarity_matrix(sentences):
    #nlp = spacy.load('en_core_web_md')
    # Create a matrix of similarity scores between each sentence
    similarity_matrix = np.zeros((len(sentences), len(sentences)))
    for i, sentence in enumerate(sentences):
        doc = nlp(sentence)
        for j, other_sentence in enumerate(sentences):
            if i == j:
                continue
            doc2 = nlp(other_sentence)
            similarity_matrix[i][j] = cosine_similarity(doc.vector.reshape(1,-1), doc2.vector.reshape(1,-1))[0][0]
    return similarity_matrix

def summarize_transcript2(transcript, language):
    
    # Compute the duration of each 5 minute interval
    interval_duration = 5 * 60  # 5 minutes in seconds
    num_intervals = math.ceil(transcript[-1]['start'] / interval_duration)  # Round up to the nearest interval
    interval_durations = [interval_duration] * num_intervals

    interval_durations[-1] = transcript[-1]['start'] % interval_duration
    
    # Extract the text property from the transcript
    text = ' '.join([d['text'] for d in transcript])
    
    # Use TextRank to segment the text
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents]
    similarity_matrix = create_similarity_matrix(sentences)
    scores = pagerank(similarity_matrix)
    ranked_sentences = [sentence for score, sentence in sorted(zip(scores, sentences), reverse=True)]
    segment_size = int(len(ranked_sentences) / num_intervals) + 1
    segments = [ranked_sentences[i:i+segment_size] for i in range(0, len(ranked_sentences), segment_size)]
    
    # Summarize each segment using GPT-3
    text_by_interval = []
    start_time = 0
    for i, segment in enumerate(segments):
        # Compute the end time of the interval
        end_time = (i+1) * interval_duration
        
        # Combine the sentences in the segment into a single string
        segment_text = ' '.join(segment)
        
        #Summarize the segment using GPT-3
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=f"Write a concise summary of the following using GPT-3:\n\n{segment_text}\n\n CONCISE SUMMARY:",
            max_tokens=2000,
            n=1,
            stop=None,
            temperature=0.5,
        )
        summary = response.choices[0].text.strip()
        summary = summarize_text_turbo(segment_text)
        
        # Create a dictionary object for the interval
        obj = {'start_time': "{:.2f}".format(start_time/60), 'end_time': "{:.2f}".format(end_time/60), 'text': summary[0].replace('\n', "<br />")}
        #obj = {'start_time': "{:.2f}".format(start_time/60), 'end_time': "{:.2f}".format(end_time/60), 'text': summary.replace('\n', "<br />")}
        text_by_interval.append(obj)
        
        # Update the start time of the next interval
        start_time = end_time

    return text_by_interval, None



def debug(text):
    with open('debug.txt', 'a') as f:
        f.write(str(text))

def summarize_transcript(transcript, language):
    # Compute the duration of each 5 minute interval
    interval_duration = 5 * 60  # 5 minutes in seconds
    num_intervals = math.ceil(transcript[-1]['start'] / interval_duration)  # Round up to the nearest interval
    interval_durations = [interval_duration] * num_intervals

    interval_durations[-1] = transcript[-1]['start'] % interval_duration
    # Extract the text property from each 5 minute interval
    text_by_interval = []
    start_time1 = 0
    for duration in interval_durations:
        end_time1 = start_time1 + duration
        
        text1 = [d['text'] for d in transcript if start_time1 <= d['start'] < end_time1]
        text1 = ' '.join(text1)
        text1 = summarize_text_turbo(text1, language=language)

        obj = {'start_time': "{:.2f}".format(start_time1/60), 'end_time': "{:.2f}".format(end_time1/60), 'text': text1[0].replace('\n', "<br />")}

        text_by_interval.append(obj)
        start_time1 = end_time1

    return  text_by_interval, None

def summarize_text(text, language):
    try:
        headers = {'Authorization': f'Bearer {API_KEY}'}
        prompt = """Write a concise summary of the following using GPT-3:


        <<SUMMARY>>


        CONCISE SUMMARY:"""

        prompt = prompt.replace('<<SUMMARY>>', text)
        #prompt = prompt.encode(encoding='ASCII', errors='ignore').decode()

        # Summarize the text in English
        data = {
            'prompt': prompt,
            'model': "text-davinci-002",
            'max_tokens': 2000,
            'temperature': 0.5,
            'top_p': 1,
            'n': 1,
        }

        #response = requests.post('https://api.openai.com/v1/engines/davinci/completions', headers=headers, json=data)
        response = requests.post('https://api.openai.com/v1/completions', headers=headers, json=data)
        summary = response.json()['choices'][0]['text'].strip()
        
        return summary, None
    except Exception as e:
        trace = traceback.format_exc()
        error_message = f"An error occurred: {str(e)} <br />trace: {trace } <br />{response.json()}"
        return None, error_message


def summarize_text_turbo(text, model="gpt-3.5-turbo", temp=0,  language="English"):
    try:
        prompt = """Write a summarize version of the following [text]
        If possible make a title
        Always format the output [text] in modern HTML with headers, bullets.
        Write the [text] in <<LANG>>
        The [text] is : <<SUMMARY>>"""

        prompt = prompt.replace('<<LANG>>', language)
        prompt = prompt.replace('<<SUMMARY>>', text)
        #prompt = prompt.encode(encoding='ASCII', errors='ignore').decode()

        conversation = list()
        conversation.append({'role': 'system', 'content': '''I am a professional copywriter assistant who will always provide thorough, professional, and detailed help.'''})
        conversation.append({'role': 'user', 'content': prompt})
        response = openai.ChatCompletion.create(model=model, messages=conversation, temperature=temp)
        summary = response['choices'][0]['message']['content']
        return summary, None
    except Exception as e:
        trace = traceback.format_exc()
        error_message = f"An error occurred: {str(e)} <br />trace: {trace } <br />{response.json()}"
        return None, error_message

if __name__ == '__main__':
    openai.api_key = API_KEY
    app.run(debug=True)
