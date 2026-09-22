from conftest import MOCK_TAMPERED_ROR
from pcl_exchange.builder import PCLMessageBuilder
from pcl_exchange.crypto import Signer, Verifier
from pcl_exchange.models import PCLMeasurementRequestContent

def test_signature_verification_success(key_pair, builder_defaults, valid_payload_data):
    """A correctly signed message should verify True."""
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(
        PCLMeasurementRequestContent.create(
            instrument_ref={"@id": valid_payload_data["instrument"]},
            sample_ref={"@id": valid_payload_data["sample"]},
            method_ref={"@id": valid_payload_data["method"]},
            params=valid_payload_data["params"],
        )
    )
    builder.set_envelope_metadata(
        project="doi:10.5072/project.0001",
        sample=valid_payload_data["sample"],
        capabilities=["xrd.powder.theta-2theta"],
    )
    signer = Signer(private_key=key_pair) 
    builder.sign(signer)
    message = builder.build()
    
    verifier = Verifier(public_key=key_pair) 
    
    envelope = next(item for item in message.graph if item.id == "#envelope")
    assert verifier.verify(envelope) is True

def test_tampered_payload_fails(key_pair, builder_defaults, valid_payload_data):
    """Modifying signed envelope metadata after signing should cause verification to fail."""
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_payload(
        PCLMeasurementRequestContent.create(
            instrument_ref={"@id": valid_payload_data["instrument"]},
            sample_ref={"@id": valid_payload_data["sample"]},
            method_ref={"@id": valid_payload_data["method"]},
            params=valid_payload_data["params"],
        )
    )
    builder.set_envelope_metadata(
        project="doi:10.5072/project.0001",
        sample=valid_payload_data["sample"],
        capabilities=["xrd.powder.theta-2theta"],
    )
    signer = Signer(private_key=key_pair)
    builder.sign(signer)
    message = builder.build()
    
    envelope_node = next(item for item in message.graph if item.id == "#envelope")
    envelope_node.receiver = MOCK_TAMPERED_ROR
    
    verifier = Verifier(public_key=key_pair)
    envelope = envelope_node
    
    assert verifier.verify(envelope) is False