import streamlit as st


def configure_page():
    st.set_page_config(
        page_title="Analizador de Balances IA",
        layout="wide",
        page_icon="📊",
    )
    st.markdown(
        """
        <style>
        button[data-testid="stBaseButton-header"] {display: none !important;}
        .processing-dots {
            display: flex; justify-content: center; gap: 10px; padding: 30px 0;
        }
        .processing-dots span {
            width: 14px; height: 14px; border-radius: 50%;
            background: #ff4b4b;
            animation: bounce 1.4s ease-in-out infinite both;
        }
        .processing-dots span:nth-child(1) { animation-delay: -0.32s; }
        .processing-dots span:nth-child(2) { animation-delay: -0.16s; }
        .processing-dots span:nth-child(3) { animation-delay: 0s; }
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        div[data-testid="stStatusWidget"] {
            border: 2px solid transparent;
            transition: border-color 0.3s ease;
        }
        div[data-testid="stStatusWidget"]:has(div[role="status"]) {
            animation: glow-pulse 1.5s ease-in-out infinite;
        }
        @keyframes glow-pulse {
            0% { border-color: rgba(255, 75, 75, 0.1); box-shadow: 0 0 5px rgba(255, 75, 75, 0.1); }
            50% { border-color: rgba(255, 75, 75, 0.6); box-shadow: 0 0 15px rgba(255, 75, 75, 0.3); }
            100% { border-color: rgba(255, 75, 75, 0.1); box-shadow: 0 0 5px rgba(255, 75, 75, 0.1); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )