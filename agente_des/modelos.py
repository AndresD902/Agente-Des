"""Contratos de entrada compartidos por el servidor y el agente."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Capacidad = Literal[1, 2, 3]
CAPACIDADES: tuple[Capacidad, ...] = (1, 2, 3)
Positivo = Annotated[FiniteFloat, Field(gt=0)]
NoNegativo = Annotated[FiniteFloat, Field(ge=0)]
Personas = Annotated[int, Field(ge=1, le=100)]
Replicas = Annotated[int, Field(ge=30, le=100)]
Semilla = Annotated[int, Field(ge=0)]


class Contrato(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Exponencial(Contrato):
    tipo: Literal["exponencial"]
    media: Positivo


class Triangular(Contrato):
    tipo: Literal["triangular"]
    minimo: Positivo
    moda: Positivo
    maximo: Positivo

    @model_validator(mode="after")
    def comprobar_orden(self):
        if not self.minimo < self.moda < self.maximo:
            raise ValueError("La triangular requiere mínimo < moda < máximo.")
        return self


class Uniforme(Contrato):
    tipo: Literal["uniforme"]
    minimo: Positivo
    maximo: Positivo

    @model_validator(mode="after")
    def comprobar_orden(self):
        if not self.minimo < self.maximo:
            raise ValueError("La uniforme requiere mínimo < máximo.")
        return self


Servicio = Annotated[Triangular | Uniforme, Field(discriminator="tipo")]


class Escenario(Contrato):
    personas: Personas
    llegadas: Exponencial
    servicio: Servicio
    replicas: Replicas
    semilla_base: Semilla


ESCENARIO_INICIAL = Escenario(
    personas=20,
    llegadas=Exponencial(tipo="exponencial", media=2),
    servicio=Triangular(tipo="triangular", minimo=1, moda=3, maximo=5),
    replicas=30,
    semilla_base=2026,
)


class CambioServicio(Contrato):
    tipo: Literal["triangular", "uniforme"] | None = None
    minimo: Positivo | None = None
    moda: Positivo | None = None
    maximo: Positivo | None = None


class CambioEscenario(Contrato):
    personas: Personas | None = None
    media_llegadas: Positivo | None = None
    servicio: CambioServicio | None = None
    replicas: Replicas | None = None
    semilla_base: Semilla | None = None

    def aplicar(self, previo: Escenario | None) -> Escenario:
        datos = previo.model_dump() if previo else {}
        cambios = self.model_dump(exclude_none=True)
        for campo in ("personas", "replicas", "semilla_base"):
            if campo in cambios:
                datos[campo] = cambios[campo]
        if self.media_llegadas is not None:
            datos["llegadas"] = {"tipo": "exponencial", "media": self.media_llegadas}
        if "servicio" in cambios:
            anterior = datos.get("servicio", {})
            nuevo = cambios["servicio"]
            if nuevo.get("tipo", anterior.get("tipo")) != anterior.get("tipo"):
                anterior = {}
            datos["servicio"] = anterior | nuevo
        return Escenario.model_validate(datos)
