"""Model data inti untuk pipeline NLU dan manajemen dialog SIGAP."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class PesanMasuk:
    teks: str
    adalah_tombol: bool = False
    waktu_epoch: float = 0.0


@dataclass
class Sesi:
    bencana_terakhir: Optional[str] = None
    fase_terakhir: Optional[str] = None
    intent_terakhir: Optional[str] = None
    status: str = "IDLE"              # IDLE | MENUNGGU_KLARIFIKASI | MODE_DARURAT
    klarifikasi_untuk: Optional[str] = None
    fallback_berturut: int = 0
    aktivitas_terakhir: float = 0.0

    def ke_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def dari_dict(d: Optional[dict]) -> "Sesi":
        if not isinstance(d, dict) or not d:
            return Sesi()
        valid_keys = {
            "bencana_terakhir",
            "fase_terakhir",
            "intent_terakhir",
            "status",
            "klarifikasi_untuk",
            "fallback_berturut",
            "aktivitas_terakhir",
        }
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        try:
            sesi = Sesi(**filtered)
            if sesi.status not in ("IDLE", "MENUNGGU_KLARIFIKASI", "MODE_DARURAT"):
                sesi.status = "IDLE"
            if not isinstance(sesi.fallback_berturut, int) or sesi.fallback_berturut < 0:
                sesi.fallback_berturut = 0
            if not isinstance(sesi.aktivitas_terakhir, (int, float)):
                sesi.aktivitas_terakhir = 0.0
            return sesi
        except Exception:
            return Sesi()


@dataclass(frozen=True)
class KandidatIntent:
    tag: str
    skor_mentah: float
    confidence: float


@dataclass(frozen=True)
class HasilNLU:
    teks_bersih: str
    darurat: bool
    entity: dict
    kandidat: list
    terpilih: Optional[KandidatIntent]
    ambigu: bool


@dataclass(frozen=True)
class Tombol:
    label: str
    payload: str


@dataclass(frozen=True)
class Balasan:
    teks: str
    tombol: list = field(default_factory=list)
    id_respons: Optional[str] = None
    darurat: bool = False


@dataclass(frozen=True)
class Keputusan:
    nlu: HasilNLU
    aksi: str  # jawab | klarifikasi | fallback | tolak | darurat | sapaan

