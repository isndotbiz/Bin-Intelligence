from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class BIN(Base):
    """BIN (Bank Identification Number) information"""
    __tablename__ = 'bins'
    
    id = Column(Integer, primary_key=True)
    bin_code = Column(String(6), unique=True, nullable=False, index=True)
    issuer = Column(String(100))
    brand = Column(String(50))
    card_type = Column(String(20))  # 'credit', 'debit', etc.
    prepaid = Column(Boolean, default=False)
    country = Column(String(2))  # ISO country code
    threeds1_supported = Column(Boolean, default=False)
    threeds2_supported = Column(Boolean, default=False)
    patch_status = Column(String(20))  # 'Patched' or 'Exploitable'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # New fields for Neutrino API verification
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    data_source = Column(String(50), default="binlist.net")  # Source of the BIN data
    issuer_website = Column(String(200), nullable=True)  # Additional info from verification
    issuer_phone = Column(String(50), nullable=True)  # Additional info from verification
    
    # Relationships
    exploits = relationship("BINExploit", back_populates="bin", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<BIN(bin_code='{self.bin_code}', brand='{self.brand}', issuer='{self.issuer}')>"


class ExploitType(Base):
    """Exploit type classification"""
    __tablename__ = 'exploit_types'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    bin_exploits = relationship("BINExploit", back_populates="exploit_type")
    
    def __repr__(self):
        return f"<ExploitType(name='{self.name}')>"


class BINExploit(Base):
    """Association between BINs and exploit types with frequency data"""
    __tablename__ = 'bin_exploits'
    
    id = Column(Integer, primary_key=True)
    bin_id = Column(Integer, ForeignKey('bins.id'), nullable=False)
    exploit_type_id = Column(Integer, ForeignKey('exploit_types.id'), nullable=False)
    frequency = Column(Integer, default=1)  # How many times this BIN was seen with this exploit
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bin = relationship("BIN", back_populates="exploits")
    exploit_type = relationship("ExploitType", back_populates="bin_exploits")
    
    def __repr__(self):
        return f"<BINExploit(bin='{self.bin.bin_code if self.bin else None}', type='{self.exploit_type.name if self.exploit_type else None}', frequency={self.frequency})>"


class ScanHistory(Base):
    """History of data scans performed"""
    __tablename__ = 'scan_history'
    
    id = Column(Integer, primary_key=True)
    scan_date = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50))  # e.g., 'pastebin', 'twitter', etc.
    bins_found = Column(Integer, default=0)
    bins_classified = Column(Integer, default=0)
    scan_parameters = Column(String(200))  # JSON string of parameters
    
    def __repr__(self):
        return f"<ScanHistory(date='{self.scan_date}', source='{self.source}', bins_found={self.bins_found})>"