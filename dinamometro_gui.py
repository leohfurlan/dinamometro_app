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
        self.root.title("Leitor de Célula de Carga v2.0 (com Gráfico)")
        # Aumentamos o tamanho da janela para acomodar o gráfico
        self.root.geometry("800x650") 
        self.root.resizable(True, True)

        # Variáveis de estado
        self.serial_connection = None
        self.is_connected = False
        self.is_recording = False
        self.start_time = 0
        self.output_file = None

        # Listas para armazenar os dados do gráfico
        self.time_data = []
        self.force_data = []

        # --- Interface Gráfica ---
        self.create_widgets()

    def create_widgets(self):
        # --- Frame Principal ---
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Frame do Gráfico (ocupará a maior parte do espaço) ---
        graph_frame = ttk.LabelFrame(main_frame, text="Gráfico Força vs. Tempo")
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Criação da figura e do eixo do Matplotlib
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Ensaio em Tempo Real")
        self.ax.set_xlabel("Tempo (s)")
        self.ax.set_ylabel("Força (N)")
        self.ax.grid(True)
        # Inicializa a linha do gráfico que será atualizada
        self.line, = self.ax.plot(self.time_data, self.force_data, 'r-')

        # Cria o canvas do Tkinter que conterá o gráfico
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- Frame de Controles (abaixo do gráfico) ---
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, expand=False)
        
        # Display de Força (agora menor, ao lado dos controles)
        display_frame = ttk.LabelFrame(bottom_frame, text="Leitura", padding=10)
        display_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.force_label = ttk.Label(display_frame, text="--- N", font=("Helvetica", 28, "bold"), foreground="blue")
        self.force_label.pack(pady=5, padx=10)
        
        # Frame de configuração e gravação
        controls_frame = ttk.Frame(bottom_frame)
        controls_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Sub-frame de Conexão
        connection_frame = ttk.LabelFrame(controls_frame, text="Configuração", padding=5)
        connection_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        ttk.Label(connection_frame, text="Porta:").grid(row=0, column=0, sticky="w")
        self.port_combobox = ttk.Combobox(connection_frame, width=12)
        self.port_combobox['values'] = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combobox.grid(row=0, column=1, padx=5)

        ttk.Label(connection_frame, text="Baud:").grid(row=0, column=2, sticky="w")
        self.baud_entry = ttk.Entry(connection_frame, width=8)
        self.baud_entry.insert(0, "9600")
        self.baud_entry.grid(row=0, column=3, padx=5)

        self.connect_button = ttk.Button(connection_frame, text="Conectar", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=4, padx=5)
        
        # Sub-frame de Gravação
        record_frame = ttk.LabelFrame(controls_frame, text="Gravação", padding=5)
        record_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        ttk.Label(record_frame, text="Arquivo:").grid(row=0, column=0, sticky="w")
        self.filename_entry = ttk.Entry(record_frame, width=22)
        self.filename_entry.insert(0, "ensaio_tracao_01.txt")
        self.filename_entry.grid(row=0, column=1, padx=5)
        
        self.record_button = ttk.Button(record_frame, text="Iniciar Gravação", command=self.toggle_recording, state="disabled")
        self.record_button.grid(row=0, column=2, padx=5)

        # Status Bar
        self.status_bar = ttk.Label(self.root, text="Status: Desconectado", relief=tk.SUNKEN, anchor="w")
        self.status_bar.pack(side="bottom", fill="x")

    def toggle_connection(self):
        # (Lógica de conexão/desconexão idêntica à versão anterior)
        if not self.is_connected:
            port = self.port_combobox.get()
            baud_rate = self.baud_entry.get()
            if not port or not baud_rate:
                messagebox.showerror("Erro", "Por favor, selecione a porta e insira o baud rate.")
                return
            try:
                self.serial_connection = serial.Serial(port, int(baud_rate), timeout=1)
                self.is_connected = True
                self.status_bar.config(text=f"Status: Conectado a {port}")
                self.connect_button.config(text="Desconectar")
                self.record_button.config(state="normal")
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
        Função que roda em uma thread separada para ler os dados da serial.
        Ela não atualiza a GUI diretamente, mas agenda a atualização na thread principal.
        """
        while self.is_connected:
            try:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    try:
                        force_value = float(line)
                        # Agenda a função de atualização da GUI para ser executada na thread principal
                        self.root.after(0, self.update_gui, force_value)
                    except (ValueError, TypeError):
                        pass
            except (serial.SerialException, OSError):
                self.is_connected = False
                self.root.after(0, self.handle_connection_error)
                break
            time.sleep(0.001) # Pausa mínima para não sobrecarregar a CPU

    def handle_connection_error(self):
        """Função para lidar com erros de conexão de forma segura para a thread."""
        messagebox.showwarning("Aviso", "A conexão com o dispositivo foi perdida.")
        self.toggle_connection() # Tenta desconectar de forma limpa
        
    def update_gui(self, force_value):
        """
        Esta função SÓ é chamada pela thread principal (via root.after).
        É seguro atualizar todos os elementos da GUI a partir daqui.
        """
        # Atualiza o label da força
        self.force_label.config(text=f"{force_value:.2f} N")

        # Se estiver gravando, adiciona dados, salva no arquivo e atualiza o gráfico
        if self.is_recording:
            elapsed_time = time.time() - self.start_time
            
            # Adiciona dados às listas para o gráfico
            self.time_data.append(elapsed_time)
            self.force_data.append(force_value)
            
            # Escreve no arquivo de texto
            if self.output_file:
                self.output_file.write(f"{elapsed_time:.4f},{force_value:.4f}\n")
            
            # Atualiza o gráfico
            self.line.set_data(self.time_data, self.force_data)
            self.ax.relim() # Recalcula os limites do eixo
            self.ax.autoscale_view() # Re-escala a visualização
            self.fig.tight_layout() # Ajusta o layout para não cortar os labels
            self.canvas.draw() # Redesenha o canvas

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
                # Atualiza o gráfico para mostrar que está limpo
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
            
            self.status_bar.config(text=f"Status: Conectado. Gravação finalizada.")
            self.record_button.config(text="Iniciar Gravação")
            self.connect_button.config(state="normal")
            self.filename_entry.config(state="normal")

    def on_closing(self):
        if self.is_connected:
            self.toggle_connection()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DinamometroApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()