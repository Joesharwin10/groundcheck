import os 
import json
import datetime
import requests
import streamlit as st
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv
MODEL_NAME      = "llama-3.3-70b-versatile"
CHUNK_SIZE      = 200
OVERLAP         = 50
N_RESULTS       = 2
LOG_FILE        = "groundcheck_logs.json"
ADMIN_PASSWORD  = "sharwin123"
load_dotenv()
client=Groq(api_key=os.getenv("GROQ_API_KEY"))
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer('all-MiniLM-L6-v2')
@st.cache_resource
def load_chroma_client():
    return chromadb.Client()
embedding_model =load_embedding_model()
chroma_client =load_chroma_client()
def log_session(username, video_url, question,
                chunks, tokens, verdict):
    entry = {
        "timestamp": datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "username":  username,
        "video_url": video_url,
        "question":  question,
        "tokens":    tokens,
        "chunks":    len(chunks),
        "verdict":   verdict
    }

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(entry)

    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2)
def extract_video_id(url):
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[1]
        video_id = video_id.split("?")[0]
    elif "youtube.com/watch" in url:
        video_id = url.split("v=")[1]
        video_id = video_id.split("&")[0]
    else:
        video_id = url.strip()
    return video_id
@st.cache_data(show_spinner=False)
@st.cache_data(show_spinner=False)
def fetch_transcript(video_id):

    import time
    import re
    import json
    import requests
    from xml.etree import ElementTree as ET

    cache_file = f"cache_{video_id}.txt"

    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()

    headers = {"User-Agent": "Mozilla/5.0"}

    # ===== METHOD 1 (HTML SCRAPE) =====
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(url, headers=headers)
        html = response.text

        match = re.search(r'"captionTracks":(\[.*?\])', html)

        if match:
            captions = json.loads(match.group(1))
            subtitle_url = captions[0]['baseUrl']

            subtitle_xml = requests.get(subtitle_url, headers=headers).text
            root = ET.fromstring(subtitle_xml)

            transcript = " ".join([
                node.text for node in root.findall('.//text') if node.text
            ])

            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(transcript)

            return transcript

    except Exception:
        pass

    # ===== METHOD 2 (FALLBACK) =====
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

        transcript = " ".join([item['text'] for item in transcript_list])

        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(transcript)

        return transcript

    except Exception:
        pass

    # ===== FINAL ERROR =====
    raise Exception("Transcript blocked by YouTube (cloud IP issue). Try another video.")
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + CHUNK_SIZE
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += CHUNK_SIZE - OVERLAP
    return chunks
def build_vector_store(chunks):
    try:
        chroma_client.delete_collection("groundcheck")
    except:
        pass
    collection = chroma_client.create_collection(
        name="groundcheck"
    )
    embeddings = embedding_model.encode(chunks).tolist()
    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[f"chunk_{i}" for i in range(len(chunks))]
    )
    return collection
def retrieve_chunks(question, collection):
    question_vector = embedding_model.encode(
        question
    ).tolist()
    results = collection.query(
        query_embeddings=[question_vector],
        n_results=N_RESULTS
    )
    return results['documents'][0]
def build_augmented_prompt(question, chunks):
    context = "\n\n".join([
        f"[Chunk {i+1}]:\n{chunk}"
        for i, chunk in enumerate(chunks)
    ])
    return f"""You are GroundCheck — a very strict AI assistant.
You answer questions ONLY from the provided context.
Never use outside knowledge under any circumstances.

CONTEXT FROM VIDEO:
{context}

QUESTION:
{question}

INSTRUCTIONS:
- Answer only from context above
- If answer not in context say exactly:
  I could not find this in the video.
- Be concise and clear
"""
def get_answer(question, collection):
    chunks = retrieve_chunks(question, collection)
    prompt = build_augmented_prompt(question, chunks)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are GroundCheck.  very Strict fact-checker. Answer only from provided context. Never use outside knowledge."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1
    )
    return {
        "answer": response.choices[0].message.content,
        "chunks": chunks
    }
def detect_hallucination(question, answer, chunks):
    context = "\n\n".join([
        f"[Chunk {i+1}]:\n{chunk}"
        for i, chunk in enumerate(chunks)
    ])
    eval_prompt = f"""You are a strict evaluation engine.

SOURCE CONTEXT:
{context}

QUESTION:
{question}

AI ANSWER TO EVALUATE:
{answer}

Respond in EXACTLY this format nothing else:

FAITHFULNESS: [1-10] | [one sentence]
COMPLETENESS: [1-10] | [one sentence]
HALLUCINATION_DETECTED: [YES or NO] | [one sentence]
OVERALL_VERDICT: [TRUSTED or FLAGGED] | [one sentence]
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "Precise evaluation engine. Respond only in exact format requested."
            },
            {
                "role": "user",
                "content": eval_prompt
            }
        ],
        temperature=0.0
    )
    return response.choices[0].message.content
def parse_evaluation(eval_text):
    lines = eval_text.strip().split('\n')
    parsed = {}

    for line in lines:
        if '|' not in line:
            continue
        left, explanation = line.split('|', 1)
        if ':' in left:
            key, score = left.split(':', 1)
            parsed[key.strip()] = {
                "score":       score.strip(),
                "explanation": explanation.strip()
            }

    return parsed
def show_admin_panel():
    st.markdown("-----")
    st.markdown("ADMIN panel")
    password = st.text_input(
        "Enter admin password",
        type="password",
        key="admin_password"
    )
    if password==ADMIN_PASSWORD:
        st.success("ACCESS GRANTED")
        if not os.path.exists(LOG_FILE):
            st.info(
                "No sessions logged yet. "
                "Wait for users to interact."
            )
            return
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)

        st.markdown(
            f"**Total sessions recorded: {len(logs)}**"
        )
        st.markdown("---")
        for i, entry in enumerate(reversed(logs)):
            with st.expander(
                f"Session {len(logs)-i} — "
                f"{entry['username']} — "
                f"{entry['timestamp']}"
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Username:**")
                    st.write(entry['username'])

                    st.markdown("**Video URL:**")
                    st.write(entry['video_url'])

                    st.markdown("**Question asked:**")
                    st.write(entry['question'])

                with col2:
                    st.markdown("**Tokens:**")
                    st.write(entry['tokens'])

                    st.markdown("**Chunks retrieved:**")
                    st.write(entry['chunks'])

                    st.markdown("**Verdict:**")
                    verdict = entry['verdict']
                    if verdict == "TRUSTED":
                        st.success(f"✅ {verdict}")
                    elif verdict == "FLAGGED":
                        st.warning(f"⚠ {verdict}")
                    else:
                        st.write(verdict)

                    st.markdown("**Timestamp:**")
                    st.write(entry['timestamp'])
        st.markdown("---")
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            log_content = f.read()

        st.download_button(
            label="Download Full Log as JSON",
            data=log_content,
            file_name="groundcheck_logs.json",
            mime="application/json"
        )

    elif password != "":
        st.error("❌ Wrong password. Access denied.")
st.set_page_config(
    page_title="GroundCheck",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
    .main-header {
        font-size: 2.8rem;
        font-weight: 700;
        color: #00C9A7;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1rem;
        color: #888888;
        margin-bottom: 2rem;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #888888;
    }
    .trusted-badge {
        background-color: #00C9A7;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
    }
    .flagged-badge {
        background-color: #FF4B4B;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)
st.markdown(
    '<p class="main-header">✅ GroundCheck</p>',
    unsafe_allow_html=True
)
st.markdown(
    '<p class="sub-header">'
    'Ask questions about any YouTube video. '
    'Get grounded, reliable answers instantly.'
    '</p>',
    unsafe_allow_html=True
)
st.markdown("---")
if "username" not in st.session_state:
    st.session_state.username = ""

if st.session_state.username == "":

    st.markdown("### 👋 Welcome — Who are you?")
    name_input = st.text_input(
        "Enter your name to continue",
    )
    if st.button("Continue", type="primary"):
        if name_input.strip() == "":
            st.warning("Please enter your name first.")
        else:
            st.session_state.username = name_input.strip()
            st.rerun()
    st.stop()
with st.sidebar:
    st.markdown(f"### {st.session_state.username}")
    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("""
1. Paste any YouTube video link
2. We read and understand the full video
3. Ask any question about the video
4. We find the most relevant parts
5. You get a reliable grounded answer
""")
    st.markdown("---")
    st.markdown("### About")
    st.markdown(
        "GroundCheck only answers from "
        "the actual video content. "
        "It never makes things up. "
        "Every answer is verified "
        "against the source."
    )
    st.markdown("---")
    show_admin = st.checkbox("Admin Panel")
    if show_admin:
        show_admin_panel()

if "collection" not in st.session_state:
    st.session_state.collection    = None
if "video_loaded" not in st.session_state:
    st.session_state.video_loaded  = False
if "transcript_info" not in st.session_state:
    st.session_state.transcript_info = None
if "current_video_url" not in st.session_state:
    st.session_state.current_video_url = ""
left_col, right_col = st.columns([1, 1], gap="large")
with left_col:
    st.markdown(
        '<div class="section-card">',
        unsafe_allow_html=True
    )
    st.markdown("### Step 1 — Load a Video")

    video_url = st.text_input(
        label="Paste YouTube URL here",
        placeholder="https://youtu.be/...",
        value=st.session_state.current_video_url
    )

    load_button = st.button(
        "Load Video",
        type="primary",
        use_container_width=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if load_button and video_url:
        with st.spinner("Building knowledge base..."):
            try:
                video_id   = extract_video_id(video_url)
                transcript = fetch_transcript(video_id)
                chunks     = chunk_text(transcript)
                collection = build_vector_store(chunks)

                st.session_state.collection        = collection
                st.session_state.video_loaded      = True
                st.session_state.current_video_url = video_url
                st.session_state.answer_result     = None
                st.session_state.verdict_value     = None
                st.session_state.transcript_info   = {
                    "characters": len(transcript),
                    "tokens":     int(len(transcript) / 4),
                    "chunks":     len(chunks)
                }
                st.success("Video loaded successfully")

            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.info(
                    "Make sure the video has "
                    "subtitles enabled."
                )

    if st.session_state.video_loaded:
        st.markdown("---")
    st.info("Video is ready — ask your question on the right")
with right_col:

    if not st.session_state.video_loaded:
        st.markdown(
            '<div class="section-card">',
            unsafe_allow_html=True
        )
        st.markdown("### Step 2 — Ask a Question")
        st.info(
            "Load a video on the left "
            "to start asking questions."
        )
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.markdown(
            '<div class="section-card">',
            unsafe_allow_html=True
        )
        st.markdown("### Step 2 — Ask a Question")

        question = st.text_input(
            label="What do you want to know?",
            placeholder="e.g. What is cyber security?"
        )

        ask_button = st.button(
            "Ask GroundCheck",
            type="primary",
            use_container_width=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if ask_button and question:
            with st.spinner("Generating answer..."):
                result = get_answer(
                    question,
                    st.session_state.collection
                )
                evaluation = detect_hallucination(
                    question=question,
                    answer=result['answer'],
                    chunks=result['chunks']
                )
                parsed        = parse_evaluation(evaluation)
                verdict_value = "UNKNOWN"
                if "OVERALL_VERDICT" in parsed:
                    verdict_value = parsed[
                        "OVERALL_VERDICT"
                    ]["score"]

                st.session_state.answer_result = result
                st.session_state.verdict_value = verdict_value

                log_session(
                    username  = st.session_state.username,
                    video_url = st.session_state.current_video_url,
                    question  = question,
                    chunks    = result['chunks'],
                    tokens    = st.session_state.transcript_info['tokens'],
                    verdict   = verdict_value
                )

        if st.session_state.answer_result is not None:
            st.markdown("---")
            st.markdown("### Answer")
            st.write(
                st.session_state.answer_result['answer']
            )
            st.markdown("---")

            verdict = st.session_state.verdict_value
            if verdict == "TRUSTED":
                st.success(
                    "This answer is grounded in the video"
                )
            elif verdict == "FLAGGED":
                st.warning(
                    "This answer may contain "
                    "unverified information"
                )
            else:
                st.info("Reliability check completed")

st.markdown("---")
st.markdown(
    "Built with LLM + RAG + Prompt Engineering "
    "| GroundCheck by Joe Sharwin"
)
