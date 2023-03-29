import math
import traceback
from flask import Flask, render_template, request, flash, redirect
import openai
from youtube_transcript_api import YouTubeTranscriptApi
import json
import requests
import textwrap

app = Flask(__name__)
app.secret_key = 'my_secret_key_1234'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_url = request.form['video_url']
        language = request.form['language']
        transcript = get_transcript(video_url)
        summarized_transcript, error = summarize_transcript(transcript, language)
        
        #flash(summarized_transcript)
        if error:
            flash(error)
            return redirect('/')
        return render_template('index.html', summary_array=summarized_transcript)
    return render_template('index.html')

def get_transcript(video_url):
    _id = video_url.split("=")[1].split("&")[0]
    transcript = YouTubeTranscriptApi.get_transcript(_id)
    return transcript

API_KEY = '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'

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
        prompt = """Act as professional copywriter, write a summarize version of the following text, in the next paragraph add in form of bullet points the highlight of it most important element with a short description in few words.
        write the text in Portuguese
        The text is : <<SUMMARY>>"""

        prompt = prompt.replace('<<SUMMARY>>', text)
        #prompt = prompt.encode(encoding='ASCII', errors='ignore').decode()

        # Summarize the text in English
        data = {
            'prompt': prompt,
            'model': "text-davinci-003",
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
        flash(summary)
        return summary, None
    except Exception as e:
        trace = traceback.format_exc()
        error_message = f"An error occurred: {str(e)} <br />trace: {trace } <br />{response.json()}"
        return None, error_message

if __name__ == '__main__':
    openai.api_key = API_KEY
    app.run(debug=True)
