# Import stuff
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_restful import Api, Resource
import os
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import google.generativeai as genai
import numpy as np
from langchain_community.vectorstores import FAISS
from langchain.schema.embeddings import Embeddings
from langchain.chains import ConversationalRetrievalChain
from langchain_google_genai import ChatGoogleGenerativeAI

# Load the API key from .env file
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

app = Flask(__name__)
api = Api(app)

# This is just a simple embedding class since we don't have real embedding models
class MyEmbeddings(Embeddings):
    def embed_documents(self, texts):
        # Just make up some vectors
        result = []
        for text in texts:
            # Use hash to make it deterministic
            seed = hash(text) % 10000
            np.random.seed(seed)
            result.append(np.random.rand(768).tolist())
        return result
    
    def embed_query(self, text):
        # Same for queries
        seed = hash(text) % 10000
        np.random.seed(seed)
        return np.random.rand(768).tolist()

# Global variables to store our stuff
documents = None
vectorstore = None
conversation_chain = None
chat_history = []
is_data_loaded = False

# API endpoint to load data
class LoadData(Resource):
    def get(self):
        global documents, vectorstore, conversation_chain, is_data_loaded
        
        try:
            # Step 1: Load the webpage
            print("Loading BrainLox website...")
            loader = WebBaseLoader("https://brainlox.com/courses/category/technical")
            documents = loader.load()
            
            # Step 2: Split the documents
            print("Splitting text...")
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            chunks = splitter.split_documents(documents)
            
            # Step 3: Make embeddings and store them
            print("Creating embeddings...")
            embeddings = MyEmbeddings()
            vectorstore = FAISS.from_documents(chunks, embeddings)
            
            # Step 4: Create the conversation chain
            print("Setting up chat...")
            llm = ChatGoogleGenerativeAI(model="models/gemini-1.5-pro", temperature=0)
            conversation_chain = ConversationalRetrievalChain.from_llm(
                llm=llm,
                retriever=vectorstore.as_retriever(search_kwargs={"k": 3})
            )
            
            is_data_loaded = True
            return {"message": "Data loaded successfully"}, 200
        except Exception as e:
            return {"error": str(e)}, 500

# API endpoint to ask questions
class AskQuestion(Resource):
    def post(self):
        global conversation_chain, chat_history
        
        if not conversation_chain:
            return {"error": "You need to load data first"}, 400
        
        # Get the question from the request
        data = request.get_json()
        if not data or "question" not in data:
            return {"error": "No question provided"}, 400
        
        question = data["question"]
        
        try:
            # Get answer from conversation chain
            response = conversation_chain.invoke({
                "question": question,
                "chat_history": chat_history
            })
            
            # Add to chat history
            chat_history.append((question, response["answer"]))
            
            return {"answer": response["answer"]}, 200
        except Exception as e:
            return {"error": str(e)}, 500

# API endpoint to reset chat history
class ResetChat(Resource):
    def post(self):
        global chat_history
        chat_history = []
        return {"message": "Chat history reset"}, 200

# Register the API endpoints
api.add_resource(LoadData, "/api/load")
api.add_resource(AskQuestion, "/api/ask")
api.add_resource(ResetChat, "/api/reset")

# Web routes for the GUI
@app.route("/")
def home():
    global is_data_loaded, chat_history
    return render_template("index.html", 
                           is_data_loaded=is_data_loaded,
                           chat_history=chat_history)

@app.route("/load-data", methods=["POST"])
def load_data():
    # Call the API to load data
    response = LoadData().get()
    return redirect(url_for("home"))

@app.route("/ask", methods=["POST"])
def ask():
    global chat_history, conversation_chain
    
    if not conversation_chain:
        return redirect(url_for("home"))
    
    question = request.form.get("question")
    
    if question:
        try:
            # Get answer directly from conversation chain
            response = conversation_chain.invoke({
                "question": question,
                "chat_history": chat_history
            })
            
            # Add to chat history
            chat_history.append((question, response["answer"]))
        except Exception as e:
            print(f"Error: {str(e)}")
    
    return redirect(url_for("home"))

@app.route("/reset", methods=["POST"])
def reset():
    global chat_history
    # Reset chat history directly
    chat_history = []
    return redirect(url_for("home"))

# Create the templates folder and the HTML template
import os

templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)

# Create the HTML template file
index_html = """
<!DOCTYPE html>
<html>
<head>
    <title>BrainLox Chatbot</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .load-section {
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f0f8ff;
            border-radius: 5px;
        }
        .chat-section {
            margin-top: 20px;
        }
        .message {
            margin-bottom: 10px;
            padding: 10px;
            border-radius: 5px;
        }
        .user-message {
            background-color: #e6f2ff;
            text-align: right;
        }
        .bot-message {
            background-color: #f0f0f0;
        }
        form {
            margin-top: 20px;
        }
        input[type="text"] {
            width: 80%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        button {
            padding: 10px 15px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover {
            background-color: #0056b3;
        }
        .status {
            color: green;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>BrainLox Chatbot</h1>
        
        <div class="load-section">
            <h2>1. Load Data</h2>
            {% if is_data_loaded %}
                <p class="status">Data loaded successfully!</p>
            {% else %}
                <p>First, you need to load data from BrainLox website</p>
                <form action="/load-data" method="post">
                    <button type="submit">Load Data</button>
                </form>
            {% endif %}
        </div>
        
        <div class="chat-section">
            <h2>2. Chat</h2>
            
            {% if is_data_loaded %}
                <div class="chat-history">
                    {% if chat_history %}
                        {% for question, answer in chat_history %}
                            <div class="message user-message">
                                <strong>You:</strong> {{ question }}
                            </div>
                            <div class="message bot-message">
                                <strong>Bot:</strong> {{ answer }}
                            </div>
                        {% endfor %}
                    {% else %}
                        <p>No messages yet. Start the conversation!</p>
                    {% endif %}
                </div>
                
                <form action="/ask" method="post">
                    <input type="text" name="question" placeholder="Ask about BrainLox technical courses..." required>
                    <button type="submit">Send</button>
                </form>
                
                <form action="/reset" method="post" style="margin-top: 10px;">
                    <button type="submit" style="background-color: #dc3545;">Reset Chat</button>
                </form>
            {% else %}
                <p>Please load the data first</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

with open(os.path.join(templates_dir, "index.html"), "w") as f:
    f.write(index_html)

# Run the app
if __name__ == "__main__":
    app.run(debug=True)