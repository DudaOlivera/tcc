import streamlit as st
import grpc
import cv2
import numpy as np
import os
import tempfile
import time
from datetime import datetime
import pymongo

st.set_page_config(
    layout="wide",
    page_title="Detector de Placas",
    page_icon="🔹",
    initial_sidebar_state="expanded"
)

def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Arquivo {file_name} não encontrado!")

load_css("style.css")

try:
    import client_pb2
    import client_pb2_grpc
except ImportError:
    st.error("client_pb2.py ou client_pb2_grpc.py não encontrados. Verifique a compilação dos protos.")

def get_mongo_collection():
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017/")
        db = client["SistemaPlacas"]
        collection = db["registros"]
        client.server_info()
        return collection
    except Exception as e:
        print(f"Erro ao conectar MongoDB: {e}")
        return None

def stream_video(video_path):
    cap = cv2.VideoCapture(video_path)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (800, 600))
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        yield client_pb2.Frame(image=buffer.tobytes())
        time.sleep(0.03) # Simula framerate
    cap.release()

def main():
    collection = get_mongo_collection()

    with st.sidebar:
        st.markdown("### 📘 Arquivo de Vídeo")
        uploaded_file = st.file_uploader("Upload", type=["mp4", "avi", "mkv"], label_visibility="collapsed")
        start_processing = False
        if uploaded_file:
            st.write("")
            start_processing = st.button("INICIAR SISTEMA")

        st.markdown("---")

        sidebar_status = st.empty()
        sidebar_status.markdown("""
        <div class="plate-container">
        <div class="plate-header">Aguardando</div>
        <div class="plate-text" style="color:#444;">---</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    crop_placeholder = st.empty()

    if collection is not None:
        st.markdown("<div style='text-align:center; color:#333; font-size:0.7rem; margin-top:20px;'>Database: Connected (MongoDB)</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='text-align:center; color:#ff4444; font-size:0.7rem; margin-top:20px;'>Database: Connection Failed</div>", unsafe_allow_html=True)

    st.markdown('<div class="main-title">Sistema de detecção e reconhecimento de placas veiculares</div>', unsafe_allow_html=True)
    video_placeholder = st.empty()
    if not start_processing:
        video_placeholder.markdown("""
        <div style="background-color:#1e1e1e; border-radius:10px; height:500px; display:flex;
        align-items:center; justify-content:center; border: 1px dashed #333;">
        <span style="color:#444; font-size:1.2rem; font-family:'Roboto';">Aguardando sinal de vídeo...</span>
        </div>
        """, unsafe_allow_html=True)

    if uploaded_file and start_processing:
        tfile = tempfile.NamedTemporaryFile(delete=False)
        tfile.write(uploaded_file.read())
        video_path = tfile.name
        tfile.close()

        last_plate = ""
        last_save_time = 0

        try:
            channel_opts = [('grpc.max_receive_message_length', 10 * 1024 * 1024)]
            with grpc.insecure_channel('localhost:50051', options=channel_opts) as channel:
                stub = client_pb2_grpc.PlateDatectorStub(channel)
                responses = stub.StreamFrames(stream_video(video_path))

                for response in responses:
                    if not response.full_image: continue

                    img_np = np.frombuffer(response.full_image, np.uint8)
                    frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

                    if response.characters:
                        sidebar_status.markdown(f"""
                        <div class="plate-container">
                        <div class="plate-header">Placa Identificada</div>
                        <div class="plate-text">{response.characters}</div>
                        </div>
                        """, unsafe_allow_html=True)

                        if response.plate_image:
                            crop_np = np.frombuffer(response.plate_image, np.uint8)
                            crop_img = cv2.imdecode(crop_np, cv2.IMREAD_COLOR)
                            crop_placeholder.image(cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB), use_container_width=True)

                        cv2.rectangle(frame, (0, 0), (200, 50), (20, 20, 20), -1)
                        cv2.rectangle(frame, (0, 0), (200, 50), (51, 153, 255), 2)
                        cv2.putText(frame, response.characters, (15, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (51, 153, 255), 2, cv2.LINE_AA)
                        current_time = time.time()
                        if collection is not None and (response.characters != last_plate or (current_time - last_save_time > 5)):
                            documento = {
                                "placa": response.characters,
                                "data_hora": datetime.now(),
                                "tipo_veiculo": getattr(response, 'plate_type', 'Desconhecido')
                            }
                            try:
                                collection.insert_one(documento)
                                last_plate = response.characters
                                last_save_time = current_time
                                print(f"Placa salva: {response.characters}")
                            except Exception as e:
                                print(f"Erro ao inserir no Mongo: {e}")

                    video_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)

        except grpc.RpcError as e:
            st.error(f"Erro de conexão gRPC: O servidor está rodando? Detalhes: {e}")
        except Exception as e:
            st.error(f"Erro geral: {e}")
        finally:
            if os.path.exists(video_path):
                os.unlink(video_path)

if __name__ == '__main__':
    main()