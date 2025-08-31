from flask import Flask, request, jsonify
   import logging

   app = Flask(__name__)

   # Логирование
   logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
   logger = logging.getLogger(__name__)

   @app.route('/input', methods=['GET', 'POST'])
   def input_handler():
       input_text = request.args.get('input', '') or request.form.get('input', '')
       logger.info(f"[INPUT] Получен ввод: {input_text}")
       response = {
           "type": "list",
           "headline": "Template",
           "template": {
               "type": "separate",
               "layout": "0,0,2,4",
               "color": "msx-glass",
               "icon": "msx-white-soft:movie",
               "iconSize": "medium",
               "title": "Title",
               "titleFooter": "Title Footer"
           },
           "items": [{"title": f"Item {i}"} for i in range(1, 101)]
       }
       return jsonify(response)

   @app.after_request
   def after_request(response):
       response.headers.add('Access-Control-Allow-Origin', '*')
       response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
       response.headers.add('Access-Control-Allow-Methods', 'GET,POST')
       return response

   if __name__ == '__main__':
       app.run(host='0.0.0.0', port=5000)
