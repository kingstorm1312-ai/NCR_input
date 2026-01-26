import streamlit as st

def render_section(title: str):
    """
    Hiển thị tiêu đề section với format chuẩn.
    """
    st.subheader(title)

def render_info(msg: str):
    """
    Hiển thị thông báo thông tin (Info).
    """
    st.info(msg)

def render_warning(msg: str):
    """
    Hiển thị thông báo cảnh báo (Warning).
    """
    st.warning(msg)
