class Colors:
    """
    Classe contenant les codes ANSI pour colorer le texte dans la console.
    """
    # Couleurs de texte
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BLACK = '\033[30m'
    
    # Styles de texte
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
    # Réinitialisation
    RESET = '\033[0m'
    
    @staticmethod
    def error(text):
        """Affiche un message d'erreur en rouge."""
        return f"{Colors.RED}{text}{Colors.RESET}"
    
    @staticmethod
    def success(text):
        """Affiche un message de succès en vert."""
        return f"{Colors.GREEN}{text}{Colors.RESET}"
    
    @staticmethod
    def info(text):
        """Affiche un message d'information en jaune."""
        return f"{Colors.YELLOW}{text}{Colors.RESET}"
    
    @staticmethod
    def highlight(text):
        """Met en évidence un texte en cyan."""
        return f"{Colors.CYAN}{text}{Colors.RESET}"
    
    @staticmethod
    def prompt(text):
        """Affiche un texte informatif en bleu."""
        return f"{Colors.BLUE}{text}{Colors.RESET}"
    
    @staticmethod
    def bold(text):
        """Met un texte en gras."""
        return f"{Colors.BOLD}{text}{Colors.RESET}"
    
    @staticmethod
    def underline(text):
        """Souligne un texte."""
        return f"{Colors.UNDERLINE}{text}{Colors.RESET}"