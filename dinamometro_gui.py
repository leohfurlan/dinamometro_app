import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time
import threading

# Importações para o Matplotlib
import matplotlib
matplotlib.use("TkAgg") # Define o backend do Matplotlib para o Tkinter
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class DinamometroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Leitor de Célula de Carga v3.0 (Final)")
        self.root.geometry("800x650")
        self.root.resizable(True, True)

        # Variáveis de estado da aplicação
        self.serial_connection = None
        self.is_connected = False
        self.is_recording = False
        self.start_time = 0
        self.output_file = None

        # Listas para armazenar os dados do gráfico da sessão atual
        self.time_data = []
        self.force_data = []

        # Construção da interface gráfica
        self.create_widgets()

    def create_widgets(self):
        # --- Frame Principal ---
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Frame do Gráfico ---
        graph_frame = ttk.LabelFrame(main_frame, text="Gráfico Força vs. Tempo")
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Ensaio em Tempo Real")
        self.ax.set_xlabel("Tempo (s)")
        self.ax.set_ylabel("Força (N)")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], 'r-', label='Força') # Linha vazia inicial
        self.ax.legend()
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- Frame de Controles (organizado na parte inferior) ---
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, expand=False, pady=(10, 0))
        
        display_frame = ttk.LabelFrame(bottom_frame, text="Leitura", padding=10)
        display_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.force_label = ttk.Label(display_frame, text="--- N", font=("Helvetica", 28, "bold"), foreground="blue", width=7, anchor='center')
        self.force_label.pack(pady=5, padx=10)
        
        controls_frame = ttk.Frame(bottom_frame)
        controls_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        connection_frame = ttk.LabelFrame(controls_frame, text="Configuração", padding=5)
        connection_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        ttk.Label(connection_frame, text="Porta:").grid(row=0, column=0, sticky="w", padx=5)
        self.port_combobox = ttk.Combobox(connection_frame, width=12)
        self.port_combobox['values'] = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combobox.grid(row=0, column=1, padx=5)

        ttk.Label(connection_frame, text="Baud:").grid(row=0, column=2, sticky="w", padx=5)
        self.baud_entry = ttk.Entry(connection_frame, width=8)
        self.baud_entry.insert(0, "9600")
        self.baud_entry.grid(row=0, column=3, padx=5)

        self.connect_button = ttk.Button(connection_frame, text="Conectar", command=self.toggle_connection, width=12)
        self.connect_button.grid(row=0, column=4, padx=10)
        
        record_frame = ttk.LabelFrame(controls_frame, text="Gravação", padding=5)
        record_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        ttk.Label(record_frame, text="Arquivo:").grid(row=0, column=0, sticky="w", padx=5)
        self.filename_entry = ttk.Entry(record_frame, width=30)
        self.filename_entry.insert(0, "ensaio_01.txt")
        self.filename_entry.grid(row=0, column=1, padx=5)
        
        self.record_button = ttk.Button(record_frame, text="Iniciar Gravação", command=self.toggle_recording, state="disabled", width=15)
        self.record_button.grid(row=0, column=2, padx=10)

        self.status_bar = ttk.Label(self.root, text="Status: Desconectado", relief=tk.SUNKEN, anchor="w")
        self.status_bar.pack(side="bottom", fill="x")

    def toggle_connection(self):
        if not self.is_connected:
            port = self.port_combobox.get()
            baud_rate = self.baud_entry.get()
            if not port or not baud_rate:
                messagebox.showerror("Erro", "Por favor, selecione a porta e insira o baud rate.")
                return
            try:
                self.serial_connection = serial.Serial(port, int(baud_rate), timeout=1)

                # --- COMANDO DE INICIALIZAÇÃO ---
                # Envia o comando "LE\r" (bytes 0x4C, 0x45, 0x0D) que descobrimos.
                time.sleep(0.5) # Pausa para garantir que a porta está pronta
                comando_secreto = bytes([0x4C, 0x45, 0x0D])
                self.serial_connection.write(comando_secreto)
                print(f"Comando de inicialização {repr(comando_secreto)} enviado para {port}.")
                # ------------------------------------

                self.is_connected = True
                self.status_bar.config(text=f"Status: Conectado a {port}")
                self.connect_button.config(text="Desconectar")
                self.record_button.config(state="normal")
                
                # Inicia a thread para ler os dados da serial de forma segura
                self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
                self.read_thread.start()

            except serial.SerialException as e:
                messagebox.showerror("Erro de Conexão", f"Não foi possível conectar à porta {port}.\nErro: {e}")
        else:
            if self.is_recording: self.toggle_recording()
            if self.serial_connection: self.serial_connection.close()
            
            self.is_connected = False
            self.status_bar.config(text="Status: Desconectado")
            self.connect_button.config(text="Conectar")
            self.record_button.config(state="disabled")
            self.force_label.config(text="--- N")

    def read_serial_data(self):
        """
        Função que roda em uma thread separada para não travar a GUI.
        Ela apenas lê a linha e a envia para a função 'update_gui' ser processada na thread principal.
        """
        while self.is_connected:
            try:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    if line: # Garante que a linha não está vazia
                        # Agenda a atualização da GUI para ser executada na thread principal
                        self.root.after(0, self.update_gui, line)
            except (serial.SerialException, TypeError, OSError):
                # Em caso de erro na porta (ex: desconexão física), encerra o loop
                self.is_connected = False
                self.root.after(0, self.handle_connection_error)
                break
            time.sleep(0.01) # Pequena pausa para não sobrecarregar a CPU

    def handle_connection_error(self):
        """Função para lidar com erros de conexão de forma segura para a thread."""
        messagebox.showwarning("Aviso", "A conexão com o dispositivo foi perdida.")
        if self.is_connected: self.toggle_connection()

    def update_gui(self, line):
        """
        Esta função SÓ é chamada pela thread principal (via root.after).
        É seguro atualizar todos os elementos da GUI a partir daqui.
        """
        # --- PONTO CRÍTICO FINAL: AJUSTE DE PARSING ---
        # Esta é a última parte que talvez precise de ajuste.
        # O código tenta converter a linha inteira para um número.
        # Se seu equipamento envia "Força: 12.3 N", este 'float(line)' vai falhar.
        # Descomente e adapte um dos exemplos abaixo se a leitura não aparecer.
        try:
            force_value = float(line) # Tenta a conversão direta
            
            # EXEMPLO 1: Se a linha for "Leitura: 12.34"
            # force_value = float(line.split(':')[1].strip())
            
            # EXEMPLO 2: Se a linha for "12.34 N"
            # force_value = float(line.split(' ')[0])

            # Atualiza o label numérico
            self.force_label.config(text=f"{force_value:.2f} N")

            # Se estiver gravando, salva no arquivo e atualiza o gráfico
            if self.is_recording:
                elapsed_time = time.time() - self.start_time
                self.time_data.append(elapsed_time)
                self.force_data.append(force_value)
                
                if self.output_file:
                    self.output_file.write(f"{elapsed_time:.4f},{force_value:.4f}\n")
                
                self.line.set_data(self.time_data, self.force_data)
                self.ax.relim()
                self.ax.autoscale_view()
                self.canvas.draw()
        except (ValueError, IndexError) as e:
            # Se a conversão falhar, imprime no terminal para depuração, mas não quebra o programa.
            print(f"Não foi possível converter a linha '{line}' para um número. Erro: {e}")
            pass
        # ---------------------------------------------------

    def toggle_recording(self):
        if not self.is_recording:
            filename = self.filename_entry.get()
            if not filename:
                messagebox.showerror("Erro", "Por favor, insira um nome para o arquivo.")
                return
            try:
                # Limpa os dados de ensaios anteriores
                self.time_data.clear()
                self.force_data.clear()
                self.line.set_data([], [])
                self.canvas.draw()

                self.output_file = open(filename, "w")
                self.output_file.write("Tempo (s),Forca (N)\n")
                
                self.is_recording = True
                self.start_time = time.time()
                self.status_bar.config(text=f"Status: Gravando em {filename}")
                self.record_button.config(text="Parar Gravação")
                self.connect_button.config(state="disabled")
                self.filename_entry.config(state="disabled")

            except IOError as e:
                messagebox.showerror("Erro de Arquivo", f"Não foi possível criar o arquivo.\nErro: {e}")
        else:
            self.is_recording = False
            if self.output_file:
                self.output_file.close()
                self.output_file = None
            
            self.status_bar.config(text=f"Status: Conectado. Gravação finalizada em {self.filename_entry.get()}")
            self.record_button.config(text="Iniciar Gravação")
            self.connect_button.config(state="normal")
            self.filename_entry.config(state="normal")

    def on_closing(self):
        """ Garante que tudo seja fechado corretamente ao sair. """
        if self.is_connected:
            self.is_connected = False # Para a thread de leitura
            time.sleep(0.1) # Dá tempo para a thread parar
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DinamometroApp(root)
    # Garante que a função on_closing seja chamada ao fechar a janela
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
