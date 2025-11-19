import os
import grpc
from concurrent import futures
import cv2
import numpy as np
import server_pb2
import server_pb2_grpc
import re
from datetime import datetime
import easyocr
from ultralytics import YOLO
import pymongo

mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
db = mongo_client["SistemaPlacas"]
collection = db["registros"]

plates_folder = 'plates'
full_images_folder = 'full_images'
os.makedirs(plates_folder, exist_ok=True)
os.makedirs(full_images_folder, exist_ok=True)

reader = easyocr.Reader(['pt'], gpu=True)

def is_traditional_plate(text):
    return bool(re.fullmatch(r'[A-Z]{3}[0-9]{4}', text))

def is_mercosul_plate(text):
    return bool(re.fullmatch(r'[A-Z]{3}[0-9]{1}[A-Z]{1}[0-9]{2}', text))

similarNumbers = {'B':'8','G':'6','I':'1','O':'0','S':'5','Z':'2','A':'4','D':'0'}
similarLetters = {'8':'B','6':'G','1':'I','0':'O','5':'S','2':'Z','4':'A'}

def replace_similar_characters(text, confidence):
    threshold = 0.8
    if confidence < threshold:
        return text
    text = list(text)
    for i, char in enumerate(text):
        if char in similarNumbers:
            text[i] = similarNumbers[char]
    for i, char in enumerate(text):
        if char in similarLetters:
            text[i] = similarLetters[char]
    return ''.join(text)

def enhance_image(image):
    return cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX)

def filter_plates(result):
    for item in result:
        text = ''.join(filter(str.isalnum, item[1])).upper()
        confidence = item[2]
        text = replace_similar_characters(text, confidence)
        if is_traditional_plate(text):
            return {"plate": text, "type": "Tradicional"}
        elif is_mercosul_plate(text):
            return {"plate": text, "type": "Mercosul"}
    return None

def np_image_to_bytes(image):
    _, buffer = cv2.imencode('.jpg', image)
    return buffer.tobytes()

def save_plate_image(image, label, img_index):
    filename = f"{plates_folder}/{label}_{img_index}.jpg"
    cv2.imwrite(filename, image)
    return filename

def save_full_image(image, label, img_index):
    filename = f"{full_images_folder}/full_image_{label}_{img_index}.jpg"
    cv2.imwrite(filename, image)
    return filename

model_path = '/home/duda/Documentos/projeto_placa/server/best.pt'
model = YOLO(model_path)

class PlateDatector(server_pb2_grpc.PlateDatectorServicer):
    def StreamFrames(self, request_iterator, context):
        for frame in request_iterator:
            try:
                image_data = np.frombuffer(frame.image, np.uint8)
                image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
                roi_image = enhance_image(image)

                plate_detected = False
                plate_type = "Nenhuma"
                plate_characters = ""
                plate_folder = ""
                full_image_folder = ""
                roi = None

                detections = model(roi_image, verbose=False)
                for box in detections[0].boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    roi = roi_image[y1:y2, x1:x2]

                    result = reader.readtext(roi, detail=1)
                    plate_data = filter_plates(result)

                    if plate_data:
                        plate_detected = True
                        plate_type = plate_data['type']
                        plate_characters = plate_data['plate']
                        timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                        timestamp_obj = datetime.now()
                        img_index = len(os.listdir(plates_folder))

                        plate_folder = save_plate_image(roi, plate_data['plate'], img_index)
                        full_image_folder = save_full_image(roi_image, plate_data['plate'], img_index)

                        try:
                            documento = {
                                "placa": plate_characters,
                                "tipo": plate_type,
                                "data_hora": timestamp_obj,
                                "caminho_imagem_placa": plate_folder,
                                "caminho_imagem_completa": full_image_folder,
                                "confianca_ocr": result[0][2] if result else 0.0
                            }
                            collection.insert_one(documento)
                            print(f"Placa {plate_characters} salva no banco com ID: {documento['_id']}")
                        except Exception as db_error:
                            print(f"Falha ao salvar: {db_error}")

                        break

                full_image_bytes = np_image_to_bytes(roi_image)
                plate_image_bytes = np_image_to_bytes(roi) if (plate_detected and roi is not None) else b''

                yield server_pb2.PlateResponse(
                    characters=plate_characters,
                    plate_type=plate_type,
                    plate_folder=plate_folder,
                    full_image_folder=full_image_folder,
                    plate_image=plate_image_bytes,
                    full_image=full_image_bytes,
                    timestamp=datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                )

            except Exception as e:
                print(f"Erro no servidor: {e}")
                context.set_details(str(e))
                context.set_code(grpc.StatusCode.INTERNAL)
                yield server_pb2.PlateResponse(
                    characters="", plate_type="Erro", plate_folder="", full_image_folder="", plate_image=b"", full_image=b"", timestamp=""
                )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    server_pb2_grpc.add_PlateDatectorServicer_to_server(PlateDatector(), server)
    server.add_insecure_port('[::]:50051')
    print("Servidor gRPC rodando na porta 50051 e conectado ao MongoDB...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()